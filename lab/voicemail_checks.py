"""Aceite de rota *97 em Asterisk REAL, sem PINs nem mensagens de produção.

Invites SIP TLS/SRTP autenticados chegam ao dialplan do próprio tenant;
confirma app VoiceMailMain com argumento de mailbox EXATO no canal vivo.
O laboratório não entra PIN nem autoriza acesso a gravações.
"""
from contextlib import ExitStack
import re
import time

from .sip_calls import CallPeer
from .srtp_media import SrtpMedia

CASES = (("t1", "t1-1001"), ("t2", "t2-1001"), ("t3", "t3-1001"))
METRICS = ("vm_registered", "vm_route_loaded", "vm_answered",
           "vm_exact_mailbox", "vm_no_foreign_mailbox", "vm_bye",
           "vm_channels_cleared")


def required_voicemail_checks():
    return {"vm_application_loaded"} | {
        f"{name}:{tenant}" for name in METRICS for tenant, _ in CASES
    }


def inspected_voicemail_channel(raw, endpoint, tenant):
    """Exige a mesma linha de canal, aplicação e argumentos exatos.

    Não combinar app de um canal com mailbox de outro. Nunca publicar
    os detalhes do CLI nem PINs na evidência.
    """
    if not isinstance(raw, str) or len(raw) > 1024 * 1024:
        return {"exact": False, "no_foreign": False}
    rows = [row.split("!") for row in raw.splitlines() if row.startswith("PJSIP/")]
    matching = [row for row in rows if row[0].startswith("PJSIP/" + endpoint + "-")]
    exact = any(
        len(row) >= 7 and row[5] == "VoiceMailMain"
        and row[6] == endpoint + "@" + tenant
        for row in matching
    )
    foreign = any(
        len(row) >= 7 and row[5] == "VoiceMailMain"
        and row[6] != endpoint + "@" + tenant
        for row in matching
    )
    return {"exact": exact, "no_foreign": bool(matching) and not foreign}


def exercise_voicemail(container, prepared, report):
    from .asterisk_lab import cli
    checks = report["checks"]
    checks.update({name: False for name in required_voicemail_checks()})
    report["live_voicemail_route_tested"] = False
    report["voicemail_route_cases"] = {}

    application = cli(container, "core show application VoiceMailMain")
    checks["vm_application_loaded"] = (
        "VoiceMailMain" in application and "not registered" not in application
    )
    if not checks["vm_application_loaded"]:
        raise ValueError("app_voicemail indisponível no Asterisk do laboratório")

    for tenant, name in CASES:
        report["phase"] = "voicemail:" + tenant
        route = cli(container, "dialplan show *97@" + tenant + "-internal")
        checks["vm_route_loaded:" + tenant] = (
            "VoiceMailMain" in route
            and "PJSIP_ENDPOINT" in route
            and "No such" not in route
        )
        with ExitStack() as resources:
            peer = CallPeer("127.0.0.1", 5061, prepared["ca"],
                            name, prepared["credentials"][name])
            resources.callback(peer.close)
            media = SrtpMedia()
            resources.callback(media.close)
            checks["vm_registered:" + tenant] = peer.register() == 200
            if not checks["vm_registered:" + tenant]:
                raise ValueError("registro SIP voicemail rejeitado")
            # INVITE utiliza o mesmo cliente SIP TLS autenticado usado
            # nas provas de chamadas com SRTP, mas a extensão é *97.
            dialog = peer.dial("*97", media)
            checks["vm_answered:" + tenant] = True
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                observation = inspected_voicemail_channel(
                    cli(container, "core show channels concise"), name, tenant)
                checks["vm_exact_mailbox:" + tenant] |= observation["exact"]
                checks["vm_no_foreign_mailbox:" + tenant] |= (
                    observation["exact"] and observation["no_foreign"]
                )
                if checks["vm_exact_mailbox:" + tenant] and checks["vm_no_foreign_mailbox:" + tenant]:
                    break
                time.sleep(0.1)
            checks["vm_bye:" + tenant] = peer.hangup(dialog) == 200
            peer.register(expires=0)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            channels = cli(container, "core show channels concise")
            checks["vm_channels_cleared:" + tenant] = not any(
                line.startswith("PJSIP/") for line in channels.splitlines()
            )
            if checks["vm_channels_cleared:" + tenant]:
                break
            time.sleep(0.2)
        report["voicemail_route_cases"][tenant] = {
            "answered": checks["vm_answered:" + tenant],
            "exact_mailbox": checks["vm_exact_mailbox:" + tenant],
            "no_foreign_mailbox": checks["vm_no_foreign_mailbox:" + tenant],
            "channels_cleared": checks["vm_channels_cleared:" + tenant],
        }
    report["live_voicemail_route_tested"] = all(
        checks[name] is True for name in required_voicemail_checks()
    )
