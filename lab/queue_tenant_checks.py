"""Prova SIP real do destino Queue por empresa no Asterisk descartável.

Não usa linha externa, cliente ou API; comprova apenas execução da
aplicação Queue no canal PJSIP autenticado com contexto correto.
"""
from contextlib import ExitStack
import re
import time

from .sip_calls import CallPeer
from .srtp_media import SrtpMedia

CASES = (("t1", "t1-1001"), ("t2", "t2-1001"), ("t3", "t3-1001"))
METRICS = ("queue_registered", "queue_route_loaded", "queue_answered",
           "queue_exact_tenant", "queue_no_foreign", "queue_bye",
           "queue_channels_cleared", "queue_wait_observed")


def required_queue_runtime_checks():
    return {f"{metric}:{tenant}" for metric in METRICS for tenant, _ in CASES}


def inspected_queue_channel(raw, endpoint, tenant):
    """A mesma linha deve identificar ramal, contexto, Queue e fila exata.

    t1 nunca é prefix-match de t10; nenhuma linha de outro canal
    pode completar um aceite parcial.
    """
    negative = {"exact": False, "no_foreign": False}
    if not isinstance(raw, str) or len(raw) > 1024 * 1024:
        return negative
    if not isinstance(endpoint, str) or not isinstance(tenant, str):
        return negative
    expected = "fila-" + tenant
    rows = [row.split("!") for row in raw.splitlines() if row.startswith("PJSIP/")]
    matching = [
        row for row in rows
        if row and re.fullmatch(r"PJSIP/" + re.escape(endpoint) + r"-[0-9a-f]+", row[0])
    ]
    if len(matching) != 1 or len(matching[0]) < 7:
        return negative
    row = matching[0]
    queue = row[6].split(",", 1)[0]
    in_queue = row[5] == "Queue"
    exact = (
        row[1] == tenant + "-internal"
        and row[2] == "1000"
        and in_queue
        and queue == expected
    )
    return {"exact": exact, "no_foreign": in_queue and queue == expected}


def exercise_queues(container, prepared, report):
    from .asterisk_lab import cli

    checks = report["checks"]
    checks.update({name: False for name in required_queue_runtime_checks()})
    report["live_queue_tenant_routing_tested"] = False
    report["queue_tenant_cases"] = {}
    for tenant, endpoint in CASES:
        report["phase"] = "queue-tenant:" + tenant
        route = cli(container, "dialplan show 1000@" + tenant + "-internal")
        checks["queue_route_loaded:" + tenant] = (
            "Queue(" in route and "Set(TENANT=" + tenant + ")" in route
        )
        with ExitStack() as resources:
            peer = CallPeer("127.0.0.1", 5061, prepared["ca"], endpoint,
                            prepared["credentials"][endpoint])
            resources.callback(peer.close)
            media = SrtpMedia()
            resources.callback(media.close)
            registered = peer.register() == 200
            checks["queue_registered:" + tenant] = registered
            if not registered:
                raise ValueError("registro do teste de fila não foi aceito")
            dialog = None
            try:
                dialog = peer.dial("1000", media)
                checks["queue_answered:" + tenant] = True
                deadline = time.monotonic() + 7
                first_wait = None
                while time.monotonic() < deadline:
                    observation = inspected_queue_channel(
                        cli(container, "core show channels concise"), endpoint, tenant
                    )
                    now = time.monotonic()
                    checks["queue_exact_tenant:" + tenant] |= observation["exact"]
                    checks["queue_no_foreign:" + tenant] |= (
                        observation["exact"] and observation["no_foreign"]
                    )
                    if observation["exact"]:
                        if first_wait is None:
                            first_wait = now
                        # Continuidade da MESMA chamada por >= 1 segundo
                        # na aplicação Queue, com fila e contexto exatos.
                        if now - first_wait >= 1.0:
                            checks["queue_wait_observed:" + tenant] = True
                    else:
                        first_wait = None
                    if (checks["queue_exact_tenant:" + tenant]
                            and checks["queue_no_foreign:" + tenant]
                            and checks["queue_wait_observed:" + tenant]):
                        break
                    time.sleep(0.12)
            finally:
                if dialog is not None:
                    checks["queue_bye:" + tenant] = peer.hangup(dialog) == 200
                peer.register(expires=0)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            channels = cli(container, "core show channels concise")
            checks["queue_channels_cleared:" + tenant] = not any(
                row.startswith("PJSIP/") for row in channels.splitlines()
            )
            if checks["queue_channels_cleared:" + tenant]:
                break
            time.sleep(0.2)
        report["queue_tenant_cases"][tenant] = {
            "exact_queue": checks["queue_exact_tenant:" + tenant],
            "no_foreign_queue": checks["queue_no_foreign:" + tenant],
            "waiting_observed": checks["queue_wait_observed:" + tenant],
            "released": checks["queue_channels_cleared:" + tenant],
        }
    report["live_queue_tenant_routing_tested"] = all(
        checks[name] is True for name in required_queue_runtime_checks()
    )
