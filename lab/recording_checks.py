"""MixMonitor REAL em Asterisk descartável com áudio sintético sobre SIP/TLS/SRTP.

A rota 9988 existe SOMENTE no staging do laboratório; nenhuma alteração
é feita no dialplan de produção. Prova arquivo e CDR de cada tenant, mas
NÃO comprova gravação do fluxo produtivo 1010/Queue, SSO ou volume físico.
"""
from contextlib import ExitStack
from pathlib import Path
import re
import secrets
import time

from .sip_calls import CallPeer
from .srtp_media import SrtpMedia, TONES

TENANTS = ("t1", "t2", "t3")
DESTINATION = "9988"
MIN_AUDIO_BYTES = 2000
METRICS = ("lab_mixmonitor_module", "lab_recording_registered",
           "lab_recording_answered", "lab_recording_srtp_sent",
           "lab_recording_bye", "lab_recording_file",
           "lab_recording_cdr", "lab_recording_no_foreign_file",
           "lab_recording_channels_cleared")


def required_recording_checks():
    return {f"{metric}:{tenant}" for tenant in TENANTS for metric in METRICS}


def prepare_recording_routes(prepared):
    """Inclui chamadas gravadas isoladas somente na cópia privada da configuração."""
    conf = Path(prepared["conf"])
    extension_file = conf / "extensions.conf"
    source = extension_file.read_text()
    if "AXE-LAB-MIXMONITOR-ONLY" in source:
        raise ValueError("rotas de gravação temporárias duplicadas")
    names = {}
    routes = ["\n; AXE-LAB-MIXMONITOR-ONLY: nunca transportar para produção"]
    for tenant in TENANTS:
        filename = secrets.token_hex(12) + ".wav"
        names[tenant] = filename
        routes.extend([
            f"[{tenant}-internal](+)",
            f"exten => {DESTINATION},1,Answer()",
            f" same => n,Set(CDR(accountcode)={tenant})",
            f" same => n,MixMonitor(/var/spool/asterisk/monitor/{tenant}/{filename})",
            " same => n,Wait(4)",
            " same => n,StopMixMonitor()",
            " same => n,Hangup()",
            "",
        ])
    extension_file.write_text(source.rstrip() + "\n" + "\n".join(routes))
    extension_file.chmod(0o600)
    prepared["lab_recording_filenames"] = names


def recording_cdr_matches(raw, tenant):
    """Evidência integral em UM CDR, sem prefix-match t1/t10."""
    from .call_checks import cdr_rows
    if tenant not in TENANTS:
        return False
    rows = cdr_rows(raw)
    if rows is None:
        return False
    hits = [
        row for row in rows
        if row[2] == DESTINATION
        and row[0] == tenant
        and row[1] == "1001"
        and row[3] == tenant + "-internal"
        and re.fullmatch(r"PJSIP/" + tenant + r"-1001-[0-9a-f]+", row[4]) is not None
        and row[6] == "ANSWERED"
        and row[7].isdigit() and int(row[7]) >= 1
        and re.fullmatch(r"[0-9]+\.[0-9]+", row[8]) is not None
    ]
    return len(hits) == 1


def recording_size_valid(raw):
    return (isinstance(raw, str) and raw.strip().isdigit()
            and MIN_AUDIO_BYTES <= int(raw.strip()) <= 64 * 1024 * 1024)


def exercise_recordings(container, prepared, report):
    """Executa o MixMonitor no Asterisk real e nunca publica áudio/telefones."""
    from .asterisk_lab import cli, command

    checks = report["checks"]
    checks.update({name: False for name in required_recording_checks()})
    report["real_lab_mixmonitor_tested"] = False
    report["real_production_recording_flow_tested"] = False
    report["recording_cases"] = {}
    names = prepared.get("lab_recording_filenames")
    if not isinstance(names, dict) or set(names) != set(TENANTS):
        raise ValueError("gravações de laboratório não preparadas")

    modules = cli(container, "module show like app_mixmonitor")
    loaded = "app_mixmonitor.so" in modules
    for tenant in TENANTS:
        checks["lab_mixmonitor_module:" + tenant] = loaded
    if not loaded:
        raise ValueError("MixMonitor não carregado no Asterisk do laboratório")
    for tenant in TENANTS:
        command(["docker", "exec", container, "mkdir", "-p",
                 "/var/spool/asterisk/monitor/" + tenant])

    for tenant in TENANTS:
        report["phase"] = "real-mixmonitor:" + tenant
        endpoint = tenant + "-1001"
        name = names[tenant]
        route = cli(container, f"dialplan show {DESTINATION}@{tenant}-internal")
        if "MixMonitor" not in route or tenant + "/" + name not in route:
            raise ValueError("rota temporária MixMonitor ausente no tenant")
        with ExitStack() as resources:
            peer = CallPeer("127.0.0.1", 5061, prepared["ca"],
                            endpoint, prepared["credentials"][endpoint])
            resources.callback(peer.close)
            media = SrtpMedia()
            resources.callback(media.close)
            checks["lab_recording_registered:" + tenant] = peer.register() == 200
            if not checks["lab_recording_registered:" + tenant]:
                raise ValueError("registro SIP para MixMonitor rejeitado")
            dialog = peer.dial(DESTINATION, media)
            checks["lab_recording_answered:" + tenant] = True

            if media.address is None or media.rx is None:
                raise ValueError("mídia SRTP MixMonitor não negociada")
            # Áudio PCMU inteiramente sintético: nunca tocar gravações reais.
            sent = 0
            deadline = time.monotonic() + 1.6
            while time.monotonic() < deadline:
                media.socket.sendto(media.protect(TONES[0]), media.address)
                sent += 1
                time.sleep(0.02)
            checks["lab_recording_srtp_sent:" + tenant] = sent >= 40
            checks["lab_recording_bye:" + tenant] = peer.await_hangup(dialog)
            peer.register(expires=0)

        path = "/var/spool/asterisk/monitor/" + tenant + "/" + name
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            size = command(["docker", "exec", container, "stat", "-c", "%s", path],
                           check=False)
            checks["lab_recording_file:" + tenant] = (
                size.returncode == 0 and recording_size_valid(size.stdout)
            )
            cdr = command(["docker", "exec", container, "cat",
                           "/var/log/asterisk/cdr-custom/Lab.csv"], check=False)
            checks["lab_recording_cdr:" + tenant] = (
                cdr.returncode == 0 and recording_cdr_matches(cdr.stdout, tenant)
            )
            channels = cli(container, "core show channels concise")
            checks["lab_recording_channels_cleared:" + tenant] = not any(
                line.startswith("PJSIP/") for line in channels.splitlines()
            )
            if (checks["lab_recording_file:" + tenant]
                    and checks["lab_recording_cdr:" + tenant]
                    and checks["lab_recording_channels_cleared:" + tenant]):
                break
            time.sleep(0.2)
        # Uma evidência física t1 não pode aparecer sob t2/t3, e vice-versa.
        checks["lab_recording_no_foreign_file:" + tenant] = all(
            command(["docker", "exec", container, "test", "!", "-e",
                     "/var/spool/asterisk/monitor/" + other + "/" + name],
                    check=False).returncode == 0
            for other in TENANTS if other != tenant
        )
        report["recording_cases"][tenant] = {
            "audio_created": checks["lab_recording_file:" + tenant],
            "cdr_exact": checks["lab_recording_cdr:" + tenant],
            "foreign_path_absent": checks["lab_recording_no_foreign_file:" + tenant],
            "released": checks["lab_recording_channels_cleared:" + tenant],
        }
    report["real_lab_mixmonitor_tested"] = all(
        checks[name] is True for name in required_recording_checks()
    )
