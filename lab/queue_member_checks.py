"""Laboratório real das ações de membros em Asterisk descartável, sem rede pública.

Usa os mesmos validadores e AMIClient que a API operacional, mas sem
token HTTP externo. Valida um membro DINÂMICO PJSIP por empresa.
"""
import queue
import secrets
import sys
import time
from pathlib import Path


TENANTS = ("t1", "t2", "t3")
CHECKS = (
    "join_ack", "join_event", "join_visible", "penalty_observed",
    "resume_ack", "resume_event", "leave_ack", "leave_event",
    "leave_absent", "exact_tenant",
)


def required_member_checks():
    return {f"members_{name}:{tenant}" for tenant in TENANTS for name in CHECKS} | {
        "members_ami_login", "members_no_external_dial",
    }


def prepare_members(prepared):
    """Expor o AMI só em loopback do host descartável, nunca 0.0.0.0."""
    secret = secrets.token_hex(32)
    manager = prepared["conf"] / "manager.conf"
    manager.write_text(
        "[general]\n"
        "enabled=yes\n"
        "port=5038\n"
        "bindaddr=127.0.0.1\n"
        "displayconnects=no\n"
        "\n[axe-members-lab]\n"
        "secret=" + secret + "\n"
        "read=system,call,agent\n"
        "write=agent\n"
        "deny=0.0.0.0/0.0.0.0\n"
        "permit=127.0.0.1/255.255.255.255\n"
    )
    manager.chmod(0o600)
    prepared["members_ami_username"] = "axe-members-lab"
    prepared["members_ami_secret"] = secret


def _production_modules():
    root = str(Path(__file__).resolve().parents[1] / "queue-api")
    if root not in sys.path:
        sys.path.insert(0, root)
    from ami_client import AMIClient
    from queue_membership import (
        QueueMemberTracker, validate_member_change, member_ami_action,
    )
    return AMIClient, QueueMemberTracker, validate_member_change, member_ami_action


def _wait(predicate, timeout=7):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return bool(predicate())


def exercise_members(container, prepared, report):
    """Ação AMI + evento real + CLI por t1/t2/t3 sem emitir chamadas."""
    from .asterisk_lab import cli
    AMIClient, QueueMemberTracker, validate, build_action = _production_modules()
    checks = report["checks"]
    checks.update({key: False for key in required_member_checks()})
    report["phase"] = "queue_members_real_ami"
    events = queue.Queue(maxsize=512)
    overflow = [False]
    tracker = QueueMemberTracker()

    def receive(event):
        tracker.apply_event(event)
        if event.get("Event") in ("QueueMemberAdded", "QueueMemberRemoved",
                                   "QueueMemberPause", "QueueMemberStatus"):
            try:
                events.put_nowait((
                    event.get("Event"), event.get("Queue"), event.get("Interface"),
                    event.get("Paused"),
                ))
            except queue.Full:
                overflow[0] = True

    client = AMIClient(
        "127.0.0.1", 5038, prepared["members_ami_username"],
        prepared["members_ami_secret"], on_event=receive,
    )
    try:
        client.connect_and_login(timeout=6)
        checks["members_ami_login"] = True
        for tenant in TENANTS:
            report["phase"] = "queue_members:" + tenant
            queue_name = "fila-" + tenant
            ext = tenant + "-1001"
            principal = {"tenant": tenant, "role": "supervisor"}
            base = {"queue": queue_name, "extension": ext}
            ok, err, change = validate(
                {**base, "penalty": 3, "paused": True},
                principal, [ext], "join",
            )
            if not ok:
                raise ValueError("validador rejeitou membro de laboratorio")

            # Confirma queue layout e ponto de partida: o membro usado
            # para teste nunca pertence aos membros estáticos.
            before = cli(container, "queue show " + queue_name)
            if ext in before:
                raise ValueError("membro de laboratorio ja presente")
            response = client.send_action(build_action(change, "join"))
            checks[f"members_join_ack:{tenant}"] = response.get("Response") == "Success"
            checks[f"members_join_event:{tenant}"] = _wait(
                lambda: any(row["extension"] == ext and row["membership"] == "dynamic"
                            for row in tracker.snapshot(principal)["members"]))
            checks[f"members_join_visible:{tenant}"] = _wait(
                lambda: "PJSIP/" + ext in cli(container, "queue show " + queue_name))
            checks[f"members_penalty_observed:{tenant}"] = any(
                row["extension"] == ext and row["penalty"] == 3
                for row in tracker.snapshot(principal)["members"])

            ok, err, unpause = validate(
                {**base, "paused": False, "reason": ""},
                principal, [ext], "pause",
            )
            if not ok:
                raise ValueError("validador rejeitou retomada de laboratorio")
            response = client.send_action(build_action(unpause, "pause"))
            checks[f"members_resume_ack:{tenant}"] = response.get("Response") == "Success"
            checks[f"members_resume_event:{tenant}"] = _wait(
                lambda: any(row["extension"] == ext and row["paused"] is False
                            for row in tracker.snapshot(principal)["members"]))

            ok, err, removal = validate(base, principal, [ext], "leave")
            if not ok:
                raise ValueError("validador rejeitou remocao de laboratorio")
            response = client.send_action(build_action(removal, "leave"))
            checks[f"members_leave_ack:{tenant}"] = response.get("Response") == "Success"
            checks[f"members_leave_event:{tenant}"] = _wait(
                lambda: not any(row["extension"] == ext
                                for row in tracker.snapshot(principal)["members"]))
            checks[f"members_leave_absent:{tenant}"] = _wait(
                lambda: "PJSIP/" + ext not in cli(container, "queue show " + queue_name))

            # Comparação por fila exata; t1 não é prefixo que aceite t10.
            checks[f"members_exact_tenant:{tenant}"] = all(
                row["extension"].startswith(tenant + "-")
                for row in tracker.snapshot(principal)["members"]
            ) and not any(
                event_queue == queue_name and interface != "PJSIP/" + ext
                for kind, event_queue, interface, paused in list(events.queue)
                if kind in ("QueueMemberAdded", "QueueMemberRemoved")
            )
        checks["members_no_external_dial"] = not overflow[0]
        report["queue_members_ami_control_tested"] = all(
            checks[key] for key in required_member_checks()
        )
        report["queue_members_no_external_calls"] = True
    finally:
        client.stop()
