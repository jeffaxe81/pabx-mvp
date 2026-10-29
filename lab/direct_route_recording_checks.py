"""Prova de 1010/1011 t1/t2 no Asterisk real (staging descartável).

Usa MixMonitor e CDR originais. Somente no staging troca o aviso de áudio
por NoOp e encaminha o atendimento WebRTC para endpoint SIP sintético.
Não demonstra o atendimento WebRTC original nem infraestrutura produtiva.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
import re
import time

from .sip_calls import CallPeer
from .srtp_media import SrtpMedia, exchange
from .recording_http_checks import _read_lab_wav

CASES = (("t1", "1010"), ("t1", "1011"), ("t2", "1010"), ("t2", "1011"))
METRICS = ("loaded", "registered", "answered", "srtp", "bye", "cdr",
           "wav", "unique_wav", "channels_cleared")


def required_direct_route_checks():
    return {f"direct_{metric}:{tenant}:{number}"
            for tenant, number in CASES for metric in METRICS}


def original_mixmonitor_line(tenant, number):
    if (tenant, number) not in CASES:
        raise ValueError("rota direta fora do escopo")
    prefix = "" if tenant == "t1" else "t2-"
    return (" same => n,MixMonitor(/var/spool/asterisk/monitor/"
            + "$" + "{STRFTIME(" + "$" + "{EPOCH},,%Y%m%d-%H%M%S)}-"
            + "$" + "{CALLERID(num)}-" + prefix + number + ".wav,b)")


def prepare_direct_route_checks(prepared):
    """Modifica somente quatro stanzas privadas e valida o original exato."""
    path = Path(prepared["conf"]) / "extensions.conf"
    source = path.read_text(encoding="utf-8")
    updated = source
    for tenant in ("t1", "t2"):
        head = re.search(r"(?m)^\[" + tenant + r"-internal\]$", updated)
        if head is None:
            raise ValueError("contexto direto não disponível")
        next_section = re.search(r"(?m)^\[", updated[head.end():])
        end = head.end() + next_section.start() if next_section else len(updated)
        section = updated[head.end():end]
        for number in ("1010", "1011"):
            pattern = (r"(?m)^exten => " + number
                       + r",1,Answer\(\)\n(?: same => .*\n)+")
            matches = list(re.finditer(pattern, section))
            if len(matches) != 1:
                raise ValueError("rota original ausente/duplicada")
            match = matches[0]
            route = match.group()
            target = tenant + ("-recepcao" if number == "1010" else "-recepcao-2")
            dial = f" same => n,Dial(PJSIP/{target},20,g)"
            if (any(fragment not in route for fragment in (
                original_mixmonitor_line(tenant, number),
                f" same => n,Set(CDR(accountcode)={tenant})",
                " same => n,Playback(custom/aviso-gravacao)",
                dial, " same => n,GotoIf("
            )) or route.count("MixMonitor(") != 1 or route.count(dial) != 1):
                raise ValueError("rota de produção divergente")
            staged = route.replace(
                " same => n,Playback(custom/aviso-gravacao)",
                " same => n,NoOp(AXE-LAB-AVISO-IGNORADO)"
            ).replace(dial, f" same => n,Dial(PJSIP/{tenant}-1002,20,g)")
            section = section[:match.start()] + staged + section[match.end():]
        updated = updated[:head.end()] + section + updated[end:]
    if updated == source:
        raise ValueError("dialplan de staging não mudou")
    path.write_text(updated, encoding="utf-8")
    path.chmod(0o600)
    # Salvar a versão anterior apenas na memória do processo de teste.
    # Inclui os contextos 9988 de laboratório; não toca o checkout git.
    prepared["lab_direct_route_original"] = source
    prepared["lab_direct_route_staged"] = True


def direct_cdr_reference(raw, tenant, number):
    """Aceita somente um CDR íntegro com origem e destino da mesma empresa."""
    from .call_checks import cdr_rows
    if (tenant, number) not in CASES:
        return None
    rows = cdr_rows(raw)
    if rows is None:
        return None
    found = [r for r in rows if (
        r[0] == tenant and r[1] == "1001" and r[2] == number
        and r[3] == tenant + "-internal"
        and re.fullmatch(r"PJSIP/" + tenant + r"-1001-[a-f0-9]+", r[4])
        and re.fullmatch(r"PJSIP/" + tenant + r"-1002-[a-f0-9]+", r[5])
        and r[6] == "ANSWERED" and r[7].isdigit() and int(r[7]) >= 1
        and re.fullmatch(r"[0-9]+\.[0-9]+", r[8])
    )]
    return "CDR:" + found[0][8] if len(found) == 1 else None


def recording_names(container):
    from .asterisk_lab import command
    result = command(["docker", "exec", container, "find",
                      "/var/spool/asterisk/monitor", "-maxdepth", "1",
                      "-type", "f", "-name", "*.wav", "-printf", "%f\n"])
    names = result.stdout.splitlines()
    if len(names) > 100 or any(len(name) > 240 for name in names):
        raise ValueError("spool direto de laboratório inesperado")
    return set(names)


def expected_wav_name(filename, tenant, number):
    if (tenant, number) not in CASES or not isinstance(filename, str):
        return False
    prefix = "" if tenant == "t1" else "t2-"
    return re.fullmatch(r"[0-9]{8}-[0-9]{6}-1001-"
                        + prefix + number + r"\.wav", filename) is not None


def exercise_direct_routes(container, prepared, report):
    from .asterisk_lab import cli, command
    checks = report["checks"]
    checks.update({key: False for key in required_direct_route_checks()})
    report["real_direct_route_mixmonitor_lab_tested"] = False
    report["direct_route_cases"] = {}
    if prepared.get("lab_direct_route_staged") is not True:
        raise ValueError("rota direta de staging ausente")
    directory = Path(prepared["conf"]).parent / "direct-route-wav"
    directory.mkdir(mode=0o700, exist_ok=False)
    for tenant, number in CASES:
        suffix = ":" + tenant + ":" + number
        report["phase"] = "direct-route:" + tenant + ":" + number
        route = cli(container, f"dialplan show {number}@{tenant}-internal")
        checks["direct_loaded" + suffix] = (
            "MixMonitor(" in route
            and ("-" + number + ".wav,b)") in route
            and "Dial(PJSIP/" + tenant + "-1002,20,g)" in route
            and "Set(CDR(accountcode)=" + tenant + ")" in route
        )
        if not checks["direct_loaded" + suffix]:
            raise ValueError("rota direta de gravação não carregada")
        before = recording_names(container)
        with ExitStack() as resources, ThreadPoolExecutor(max_workers=1) as pool:
            caller = CallPeer("127.0.0.1", 5061, prepared["ca"],
                              tenant + "-1001", prepared["credentials"][tenant + "-1001"])
            callee = CallPeer("127.0.0.1", 5061, prepared["ca"],
                              tenant + "-1002", prepared["credentials"][tenant + "-1002"])
            resources.callback(caller.close)
            resources.callback(callee.close)
            left, right = SrtpMedia(), SrtpMedia()
            resources.callback(left.close)
            resources.callback(right.close)
            checks["direct_registered" + suffix] = (
                caller.register() == 200 and callee.register() == 200
            )
            if not checks["direct_registered" + suffix]:
                raise ValueError("registro de ramal direto não aceito")
            pending = pool.submit(callee.answer, right)
            outgoing = caller.dial(number, left)
            incoming = pending.result(timeout=14)
            checks["direct_answered" + suffix] = True
            media = exchange(left, right, duration=1.6)
            checks["direct_srtp" + suffix] = all(
                media[k] for k in ("authenticated", "payloads_match",
                                  "tamper_rejected", "replay_rejected")
            )
            pending_bye = pool.submit(callee.await_hangup, incoming)
            checks["direct_bye" + suffix] = (
                caller.hangup(outgoing) == 200 and pending_bye.result(timeout=12)
            )
            caller.register(expires=0)
            callee.register(expires=0)
        deadline = time.monotonic() + 9
        new = set()
        while time.monotonic() < deadline:
            new = recording_names(container) - before
            cdr = command(["docker", "exec", container, "cat",
                           "/var/log/asterisk/cdr-custom/Lab.csv"], check=False)
            checks["direct_cdr" + suffix] = (
                cdr.returncode == 0
                and direct_cdr_reference(cdr.stdout, tenant, number) is not None
            )
            checks["direct_unique_wav" + suffix] = (
                len(new) == 1 and expected_wav_name(next(iter(new)), tenant, number)
            )
            channels = cli(container, "core show channels concise")
            checks["direct_channels_cleared" + suffix] = not any(
                line.startswith("PJSIP/") for line in channels.splitlines()
            )
            if all(checks[k + suffix] for k in ("direct_cdr",
                                                 "direct_unique_wav",
                                                 "direct_channels_cleared")):
                break
            time.sleep(0.2)
        if checks["direct_unique_wav" + suffix]:
            name = next(iter(new))
            target = directory / name
            command(["docker", "cp",
                     container + ":/var/spool/asterisk/monitor/" + name,
                     str(target)], timeout=20)
            target.chmod(0o600)
            try:
                checks["direct_wav" + suffix] = len(_read_lab_wav(target)) > 2000
            except ValueError:
                pass
        report["direct_route_cases"][tenant + ":" + number] = {
            "audio": checks["direct_wav" + suffix],
            "cdr": checks["direct_cdr" + suffix],
            "isolated_name": checks["direct_unique_wav" + suffix],
            "media": checks["direct_srtp" + suffix],
        }
    report["real_direct_route_mixmonitor_lab_tested"] = all(
        checks[k] is True for k in required_direct_route_checks()
    )


def restore_direct_route_checks(container, prepared):
    """Restaura a configuração privada e comprova os destinos WebRTC reais."""
    from .asterisk_lab import cli
    source = prepared.pop("lab_direct_route_original", None)
    if not isinstance(source, str) or not source or not prepared.get("lab_direct_route_staged"):
        raise ValueError("fonte original da rota direta ausente")
    path = Path(prepared["conf"]) / "extensions.conf"
    path.write_text(source, encoding="utf-8")
    path.chmod(0o600)
    result = cli(container, "dialplan reload")
    if "No such command" in result or "error" in result.lower():
        raise ValueError("reload original do dialplan não aceito")
    for tenant in ("t1", "t2"):
        for number in ("1010", "1011"):
            target = tenant + ("-recepcao" if number == "1010" else "-recepcao-2")
            route = cli(container, f"dialplan show {number}@{tenant}-internal")
            if ("Dial(PJSIP/" + target + ",20,g)" not in route
                    or "Dial(PJSIP/" + tenant + "-1002,20,g)" in route
                    or "MixMonitor(" not in route):
                raise ValueError("rota WebRTC não foi restaurada")
    prepared["lab_direct_route_staged"] = False
    prepared["lab_direct_route_restored"] = True
