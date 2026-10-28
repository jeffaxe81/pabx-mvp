"""AMI real somente no Asterisk descartável: primeira prova de OriginateResponse.

Não marca DialEnd/campanhas/callbacks como homologados. Os canais Local
não telefonam para ninguém e todos os dados AMI ficam apenas na memória.
"""
import queue
import secrets
import sys
import time
from pathlib import Path


def _production_modules():
    # Importar a mesma implementação de AMI e correlação usada pela queue-api.
    path = str(Path(__file__).resolve().parents[1] / "queue-api")
    if path not in sys.path:
        sys.path.insert(0, path)
    from ami_client import AMIClient
    from outbound_correlation import channel_id_for, matches_originate_response
    return AMIClient, channel_id_for, matches_originate_response


def prepare_ami(prepared):
    """Habilitar AMI só no namespace/host descartável, exclusivamente loopback."""
    conf = prepared["conf"]
    secret = secrets.token_hex(32)
    manager = conf / "manager.conf"
    manager.write_text(
        "[general]\n"
        "enabled=yes\n"
        "port=5038\n"
        "bindaddr=127.0.0.1\n"
        "displayconnects=no\n"
        "\n[axe-lab]\n"
        "secret=" + secret + "\n"
        "read=system,call\n"
        "write=originate,call\n"
        "deny=0.0.0.0/0.0.0.0\n"
        "permit=127.0.0.1/255.255.255.255\n"
    )
    manager.chmod(0o600)
    extensions = conf / "extensions.conf"
    # Contexto isolado e não acessível pelos ramais normais.
    with extensions.open("a") as output:
        output.write(
            "\n; AXE AMI LAB (apenas preparação descartável)\n"
            "[axe-ami-lab]\n"
            "exten => start,1,Answer()\n"
            " same => n,Wait(2)\n"
            " same => n,Hangup()\n"
            "exten => after,1,NoOp(AXE AMI Lab)\n"
            " same => n,Hangup()\n"
        )
    prepared["ami_username"] = "axe-lab"
    prepared["ami_secret"] = secret


def assess_response(event, attempt_id, channel_id, tenant="t1"):
    """Avaliar evidência real sem publicar evento, telefone ou credencial."""
    _, channel_id_for, matches = _production_modules()
    record = {"attempt_id": attempt_id, "channel_id": channel_id, "tenant": tenant}
    valid = matches(event, record)
    return {
        "ami_event_observed": isinstance(event, dict) and event.get("Event") == "OriginateResponse",
        "ami_action_channel_correlated": valid,
        "ami_originate_success": valid and event.get("Response") == "Success",
        "ami_wrong_action_rejected": not matches(
            {**event, "ActionID": "0" * 32}, record) if isinstance(event, dict) else False,
        "ami_wrong_channel_rejected": not matches(
            {**event, "Uniqueid": "axe-" + "0" * 32}, record) if isinstance(event, dict) else False,
        "ami_channel_id_format": channel_id_for(attempt_id) == channel_id,
    }


def required_ami_checks():
    return {"ami_login", "ami_action_queued", "ami_event_observed",
            "ami_action_channel_correlated", "ami_originate_success",
            "ami_wrong_action_rejected", "ami_wrong_channel_rejected",
            "ami_channel_id_format"}


def exercise_ami(prepared, report):
    """Chamar exclusivamente Local/start; sem linha pública, PJSIP ou tronco."""
    AMIClient, channel_id_for, _ = _production_modules()
    checks = report["checks"]
    for check in required_ami_checks():
        checks[check] = False
    report["live_ami_originate_response_tested"] = False
    report["live_ami_dialend_correlated"] = False
    report["phase"] = "ami_local_originate"
    attempt = secrets.token_hex(16)
    channel = channel_id_for(attempt)
    events = queue.Queue(maxsize=128)
    overflow = [False]

    def receive(event):
        if event.get("Event") == "OriginateResponse":
            try:
                events.put_nowait(event)
            except queue.Full:
                overflow[0] = True

    client = AMIClient("127.0.0.1", 5038, prepared["ami_username"],
                       prepared["ami_secret"], on_event=receive)
    try:
        client.connect_and_login(timeout=6)
        checks["ami_login"] = True
        response = client.send_action({
            "Action": "Originate",
            "Channel": "Local/start@axe-ami-lab/n",
            "Context": "axe-ami-lab",
            "Exten": "after",
            "Priority": "1",
            "Async": "true",
            "Timeout": "5000",
            "ActionID": attempt,
            "ChannelId": channel,
            "Account": "t1",
        })
        checks["ami_action_queued"] = (
            response.get("ActionID") == attempt and response.get("Response") == "Success"
        )
        deadline = time.monotonic() + 10
        matched = []
        while time.monotonic() < deadline and not overflow[0]:
            try:
                event = events.get(timeout=min(0.5, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if event.get("ActionID") == attempt:
                matched.append(event)
                if len(matched) > 1:
                    break
                if event.get("Response") in ("Success", "Failure"):
                    # Esperar brevemente para identificar evento duplicado.
                    time.sleep(0.2)
                    while not events.empty():
                        extra = events.get_nowait()
                        if extra.get("ActionID") == attempt:
                            matched.append(extra)
                    break
        if len(matched) == 1 and not overflow[0]:
            checks.update(assess_response(matched[0], attempt, channel))
        else:
            report["ami_event_count_valid"] = False
        report["live_ami_originate_response_tested"] = all(
            checks[name] for name in required_ami_checks())
    finally:
        client.stop()
