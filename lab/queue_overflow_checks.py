"""Prova de timeout e transbordo reais do dialplan Queue por empresa.

SIP/TLS + SRTP, sem ramais de clientes. Somente a extensão 9987 de
entrada é acrescentada ao staging efêmero; o código real 1000 e
fila-overflow/fazer-overflow permanece inalterado.
"""
from contextlib import ExitStack
from pathlib import Path
import re
import time

from .sip_calls import CallPeer
from .srtp_media import SrtpMedia

TENANTS = ("t1", "t2", "t3")
EXTENSION = "9987"
METRICS = ("loaded", "registered", "answered", "language_queue",
           "same_channel", "general_queue", "no_foreign_queue",
           "no_loop", "bye", "cdr", "channels_cleared")


def required_queue_overflow_checks():
    return {f"overflow_{name}:{tenant}" for name in METRICS for tenant in TENANTS}


def overflow_stanza(tenant):
    if tenant not in TENANTS:
        raise ValueError("tenant não permitido para prova de overflow")
    return (
        f"exten => {EXTENSION},1,Set(FILA_IDIOMA=fila-{tenant}-en)\n"
        " same => n,Set(OVERFLOW_TIMEOUT_SECONDS=2)\n"
        " same => n,Goto(1000,1)\n\n"
    )


def prepare_queue_overflow(prepared):
    """Só cria ponto de entrada, nunca substitui a lógica de transbordo."""
    conf = Path(prepared["conf"])
    destinations = {
        "t1": conf / "extensions.conf",
        "t2": conf / "extensions.conf",
        "t3": conf / "extensions_tenants/t3.conf",
    }
    source = {path: path.read_text(encoding="utf-8") for path in set(destinations.values())}
    staged = dict(source)
    for tenant in TENANTS:
        path = destinations[tenant]
        anchor = f"[{tenant}-internal]\n"
        body = staged[path]
        if body.count(anchor) != 1:
            raise ValueError("contexto de overflow ausente/duplicado")
        section = body.split(anchor, 1)[1].split("\n[", 1)[0]
        if f"exten => {EXTENSION}," in section:
            raise ValueError("entrada de overflow duplicada no contexto")
        if not all(x in body for x in (
            "same => n,Queue(", "same => n,GotoIf(", "fila-overflow",
            "fazer-overflow", "Set(FILA_OVERFLOW=",
        )):
            raise ValueError("dialplan de transbordo não pode ser modificado")
        staged[path] = body.replace(anchor, anchor + overflow_stanza(tenant), 1)
    for path, value in staged.items():
        path.write_text(value, encoding="utf-8")
        path.chmod(0o600)
    prepared["lab_overflow_routes_staged"] = True


def active_queue(raw, endpoint, tenant):
    """Captura a única fila ativa do próprio canal SIP autenticado.

    Retorna (ID de canal, fila), nunca compõe prova usando duas linhas.
    """
    if (not isinstance(raw, str) or len(raw) > 1024 * 1024
            or not isinstance(endpoint, str) or tenant not in TENANTS
            or endpoint != tenant + "-1001"):
        return None
    matches = []
    for line in raw.splitlines():
        if not line.startswith("PJSIP/"):
            continue
        row = line.split("!")
        if (len(row) < 7
                or not re.fullmatch(r"PJSIP/" + re.escape(endpoint) + r"-[0-9a-f]+", row[0])):
            continue
        matches.append(row)
    if len(matches) != 1:
        return None
    row = matches[0]
    if (row[1] != tenant + "-internal" or row[2] != "1000" or row[4] != "Up"
            or row[5] != "Queue"):
        return None
    queue = row[6].split(",", 1)[0]
    if queue not in {"fila-" + tenant + "-en", "fila-" + tenant}:
        return None
    return row[0], queue


def overflow_cdr_matches(raw, tenant):
    from .call_checks import cdr_rows
    if tenant not in TENANTS:
        return False
    rows = cdr_rows(raw)
    if rows is None:
        return False
    matches = [
        row for row in rows
        if (row[0] == tenant and row[1] == "1001" and row[2] == EXTENSION
            and row[3] == tenant + "-internal"
            and re.fullmatch(r"PJSIP/" + tenant + r"-1001-[0-9a-f]+", row[4])
            and row[5] == "" and row[6] == "ANSWERED"
            and row[7].isdigit() and int(row[7]) >= 2
            and re.fullmatch(r"[0-9]+\.[0-9]+", row[8]))
    ]
    return len(matches) == 1


def exercise_queue_overflow(container, prepared, report):
    from .asterisk_lab import cli, command
    checks = report["checks"]
    checks.update({name: False for name in required_queue_overflow_checks()})
    report["live_queue_overflow_tested"] = False
    report["queue_overflow_cases"] = {}
    if prepared.get("lab_overflow_routes_staged") is not True:
        raise ValueError("rota privada 9987 não instalada")
    for tenant in TENANTS:
        suffix = ":" + tenant
        endpoint = tenant + "-1001"
        report["phase"] = "queue-overflow:" + tenant
        route = cli(container, f"dialplan show {EXTENSION}@{tenant}-internal")
        original = cli(container, f"dialplan show 1000@{tenant}-internal")
        loaded_parts = (
            f"Set(FILA_IDIOMA=fila-{tenant}-en)" in route,
            "Set(OVERFLOW_TIMEOUT_SECONDS=2)" in route,
            "Goto(1000,1)" in route,
            "Queue(" in original,
            "GotoIf(" in original,
        )
        checks["overflow_loaded" + suffix] = all(loaded_parts)
        if not checks["overflow_loaded" + suffix]:
            # Só cinco booleans diagnósticos, nunca publicar dialplan/segredos.
            report["phase"] = ("queue-overflow-load:" + tenant + ":"
                               + "".join("1" if ok else "0" for ok in loaded_parts))
            raise ValueError("roteamento de transbordo não carregado")
        with ExitStack() as resources:
            peer = CallPeer("127.0.0.1", 5061, prepared["ca"],
                            endpoint, prepared["credentials"][endpoint])
            resources.callback(peer.close)
            media = SrtpMedia()
            resources.callback(media.close)
            checks["overflow_registered" + suffix] = peer.register() == 200
            if not checks["overflow_registered" + suffix]:
                raise ValueError("registro SIP de transbordo recusado")
            dialog = peer.dial(EXTENSION, media)
            checks["overflow_answered" + suffix] = True
            channel = None
            entered_language_at = None
            entered_general_at = None
            # Uma única chamada deve passar primeiro pela fila de idioma
            # e depois pela fila geral, sem voltar ao idioma (sem loop).
            deadline = time.monotonic() + 12
            no_loop = True
            steps = []
            while time.monotonic() < deadline:
                state = active_queue(
                    cli(container, "core show channels concise"), endpoint, tenant
                )
                if state is not None:
                    current_channel, queue = state
                    if channel is None:
                        channel = current_channel
                    elif current_channel != channel:
                        no_loop = False
                    if queue == "fila-" + tenant + "-en":
                        if entered_general_at is not None:
                            no_loop = False
                        if entered_language_at is None:
                            entered_language_at = time.monotonic()
                            steps.append("language")
                        checks["overflow_language_queue" + suffix] = True
                    elif queue == "fila-" + tenant:
                        if entered_general_at is None:
                            entered_general_at = time.monotonic()
                            steps.append("general")
                        checks["overflow_general_queue" + suffix] = (
                            entered_language_at is not None
                            and entered_general_at - entered_language_at >= 0.8
                        )
                    checks["overflow_no_foreign_queue" + suffix] = (
                        queue.startswith("fila-" + tenant)
                    )
                    checks["overflow_same_channel" + suffix] = (
                        channel is not None and current_channel == channel
                    )
                if (checks["overflow_language_queue" + suffix]
                        and checks["overflow_general_queue" + suffix]
                        and entered_general_at is not None
                        and time.monotonic() - entered_general_at >= 0.4):
                    break
                time.sleep(0.10)
            checks["overflow_no_loop" + suffix] = (
                no_loop and steps == ["language", "general"]
            )
            checks["overflow_bye" + suffix] = peer.hangup(dialog) == 200
            peer.register(expires=0)
        end = time.monotonic() + 8
        while time.monotonic() < end:
            channels = cli(container, "core show channels concise")
            checks["overflow_channels_cleared" + suffix] = not any(
                row.startswith("PJSIP/") for row in channels.splitlines()
            )
            cdr = command(["docker", "exec", container, "cat",
                           "/var/log/asterisk/cdr-custom/Lab.csv"], check=False)
            checks["overflow_cdr" + suffix] = (
                cdr.returncode == 0 and overflow_cdr_matches(cdr.stdout, tenant)
            )
            if (checks["overflow_channels_cleared" + suffix]
                    and checks["overflow_cdr" + suffix]):
                break
            time.sleep(0.2)
        report["queue_overflow_cases"][tenant] = {
            "language_first": checks["overflow_language_queue" + suffix],
            "general_after_timeout": checks["overflow_general_queue" + suffix],
            "same_channel": checks["overflow_same_channel" + suffix],
            "no_loop": checks["overflow_no_loop" + suffix],
            "cdr": checks["overflow_cdr" + suffix],
        }
    report["live_queue_overflow_tested"] = all(
        checks[name] is True for name in required_queue_overflow_checks()
    )
