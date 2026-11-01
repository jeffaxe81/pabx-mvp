"""REL-13: prova SIP REFER em Asterisk real isolado; sem operadora.

Comprova aceite do REFER e INVITE ao novo ramal, sem declarar áudio
após a transferência nem homologação de telefone/tronco de produção.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import re
import time

from .sip_calls import CallPeer
from .srtp_media import SrtpMedia

TENANTS = ("t1", "t2")
CHECKS = ("transfer_register", "initial_answer", "refer_202",
          "target_answer", "same_tenant_channels", "no_trunk_channels")


def required_transfer_checks():
    return {name + ":" + tenant for tenant in TENANTS for name in CHECKS}


def same_tenant_channel_lines(raw, tenant):
    """Ignora descrições/comentários; exige canais ativos da própria empresa."""
    if not isinstance(raw, str):
        return False
    channels = [row.split("!", 1)[0] for row in raw.splitlines()]
    names = [f"PJSIP/{tenant}-{n}-" for n in ("1001", "1003")]
    return all(any(line.startswith(name) for line in channels) for name in names)


def exercise_transfers(container, prepared, report):
    from .asterisk_lab import cli

    checks = report["checks"]
    checks.update({name: False for name in required_transfer_checks()})
    report["transfer_cases"] = {}
    report["sip_refer_blind_transfer_tested"] = False
    report["operator_transfer_tested"] = False
    for tenant in TENANTS:
        report["phase"] = "sip-transfer:" + tenant
        with ExitStack() as stack, ThreadPoolExecutor(max_workers=2) as executor:
            endpoints = {}
            media = {}
            for suffix in ("1001", "1002", "1003"):
                name = tenant + "-" + suffix
                peer = CallPeer("127.0.0.1", 5061, prepared["ca"], name,
                                prepared["credentials"][name])
                stack.callback(peer.close)
                endpoints[suffix] = peer
                media[suffix] = SrtpMedia()
                stack.callback(media[suffix].close)
            checks["transfer_register:" + tenant] = all(
                endpoints[suffix].register() == 200 for suffix in endpoints
            )
            if not checks["transfer_register:" + tenant]:
                raise ValueError("registro SIP da transferência falhou")

            old_answer = executor.submit(endpoints["1002"].answer, media["1002"])
            caller_dialog = endpoints["1001"].dial("1002", media["1001"])
            transfer_dialog = old_answer.result(timeout=15)
            checks["initial_answer:" + tenant] = bool(
                caller_dialog and transfer_dialog
            )
            target_answer = executor.submit(
                endpoints["1003"].answer, media["1003"]
            )
            checks["refer_202:" + tenant] = (
                endpoints["1002"].blind_transfer(transfer_dialog, "1003") == 202
            )
            # Não contar somente resposta 202: um novo INVITE ao ramal 1003
            # precisa chegar e ser atendido pelo terminal SIP de laboratorio.
            dialog_1003 = target_answer.result(timeout=15)
            checks["target_answer:" + tenant] = (
                dialog_1003 is not None
                and "invite_received" in endpoints["1003"].events
                and "ack_received" in endpoints["1003"].events
            )
            deadline = time.monotonic() + 4
            observed = ""
            while time.monotonic() < deadline:
                observed = cli(container, "core show channels concise")
                if same_tenant_channel_lines(observed, tenant):
                    break
                time.sleep(0.2)
            checks["same_tenant_channels:" + tenant] = (
                same_tenant_channel_lines(observed, tenant)
            )
            checks["no_trunk_channels:" + tenant] = not bool(
                re.search(r"(?m)^PJSIP/(?:gateway-tdm|gateway-tdm-2)-", observed)
            )
            report["transfer_cases"][tenant] = {
                "registration": checks["transfer_register:" + tenant],
                "original_dialogue": checks["initial_answer:" + tenant],
                "refer_accepted": checks["refer_202:" + tenant],
                "new_invite_answered": checks["target_answer:" + tenant],
                "correct_tenant": checks["same_tenant_channels:" + tenant],
                "no_operator_gateway": checks["no_trunk_channels:" + tenant],
            }
            # Somente ambiente Docker descartável. A limpeza efetiva do
            # container e responsabilidade do teardown comum do lab.
            cli(container, "channel request hangup all")
            for suffix in endpoints:
                try:
                    endpoints[suffix].register(expires=0)
                except (OSError, ValueError, TimeoutError):
                    # NOTIFY/BYE tardios podem alterar fluxo; não tomar
                    # unregister como prova de transferência concluída.
                    pass
    report["sip_refer_blind_transfer_tested"] = all(
        checks[name] is True for name in required_transfer_checks()
    )
