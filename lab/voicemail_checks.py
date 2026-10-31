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

# t3-1001 is a fallback mailbox in production; it only becomes a SIP
# endpoint inside this disposable --calls laboratory (prepare_calls), with
# a private generated PJSIP config and ephemeral SIP credentials. t3-recepcao
# is WebRTC/DTLS-SRTP and cannot be exercised by this SDES-SRTP SIP client.
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
    negative = {"exact": False, "no_foreign": False}
    if (not isinstance(raw, str) or len(raw) > 1024 * 1024
            or not isinstance(endpoint, str) or not isinstance(tenant, str)
            or re.fullmatch(r"t[1-9][0-9]*-[a-z0-9_-]+", endpoint) is None
            or re.fullmatch(r"t[1-9][0-9]*", tenant) is None
            or not endpoint.startswith(tenant + "-")):
        return negative
    # A prova precisa vir de UM canal PJSIP identificável, incluindo
    # contexto e extensão *97. Não juntar evidências de dois canais.
    rows = [line.split("!") for line in raw.splitlines()
            if line.startswith("PJSIP/")]
    matching = [
        row for row in rows
        if row and re.fullmatch(
            r"PJSIP/" + re.escape(endpoint) + r"-[0-9a-f]+", row[0]
        )
    ]
    if len(matching) != 1 or len(matching[0]) < 7:
        return negative
    row = matching[0]
    # Se o snapshot CLI contém outro canal em VoiceMailMain, ele também
    # precisa acessar exclusivamente sua própria mailbox. Uma linha
    # correta não mascara um acesso cruzado simultâneo.
    foreign_access = False
    for observed in rows:
        if len(observed) >= 7 and observed[5] == "VoiceMailMain":
            identity = re.fullmatch(r"PJSIP/(t[1-9][0-9]*-[a-z0-9_-]+)-[0-9a-f]+", observed[0])
            if identity is None:
                foreign_access = True
                break
            observed_endpoint = identity.group(1)
            observed_tenant = observed_endpoint.split("-", 1)[0]
            if (observed[6] != observed_endpoint + "@" + observed_tenant
                    or observed[1] != observed_tenant + "-internal"):
                foreign_access = True
                break
    exact = (row[1] == tenant + "-internal" and row[2] == "*97"
             and row[4] == "Up" and row[5] == "VoiceMailMain"
             and row[6] == endpoint + "@" + tenant)
    return {"exact": exact, "no_foreign": exact and not foreign_access}


def required_voicemail_dtmf_checks():
    """Comprova negociação/transmissão, não autenticação da caixa postal."""
    return {f'{name}:{tenant}' for name in ('vm_dtmf_negotiated',
            'vm_dtmf_sent') for tenant, _ in CASES}


def exercise_voicemail(container, prepared, report, *, dtmf=False):
    from .asterisk_lab import cli
    checks = report["checks"]
    checks.update({name: False for name in required_voicemail_checks()})
    if dtmf:
        checks.update({name: False for name in required_voicemail_dtmf_checks()})
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
        # Fail closed if the caller skipped prepare_calls: the fallback
        # mailbox is never itself a production SIP credential.
        if name not in prepared["credentials"]:
            raise ValueError("perfil SIP temporário do voicemail não provisionado")
        with ExitStack() as resources:
            peer = CallPeer("127.0.0.1", 5061, prepared["ca"],
                            name, prepared["credentials"][name])
            resources.callback(peer.close)
            media = SrtpMedia(dtmf=dtmf)
            resources.callback(media.close)
            checks["vm_registered:" + tenant] = peer.register() == 200
            if not checks["vm_registered:" + tenant]:
                raise ValueError("registro SIP voicemail rejeitado")
            # INVITE utiliza o mesmo cliente SIP TLS autenticado usado
            # nas provas de chamadas com SRTP, mas a extensão é *97.
            dialog = peer.dial("*97", media)
            checks["vm_answered:" + tenant] = True
            if dtmf:
                # O SDP precisa anunciar e aceitar RFC4733 sobre SRTP.
                # Ainda não prova que VoiceMailMain validou qualquer PIN.
                checks["vm_dtmf_negotiated:" + tenant] = (
                    media.address is not None and media.rx is not None
                )
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
            if dtmf and checks["vm_exact_mailbox:" + tenant]:
                # Um dígito sintético, insuficiente para autenticar PIN.
                # Não registrar dígitos, pacotes ou segredos em relatórios.
                media.send_dtmf('1')
                checks["vm_dtmf_sent:" + tenant] = True
            bye = (peer.hangup_or_accept_remote_bye(dialog) if dtmf
                   else peer.hangup(dialog))
            checks["vm_bye:" + tenant] = bye == 200
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
    if dtmf:
        report["voicemail_dtmf_transport_only"] = all(
            checks[name] is True for name in required_voicemail_dtmf_checks()
        )
        report["voicemail_pin_authentication_verified"] = False
