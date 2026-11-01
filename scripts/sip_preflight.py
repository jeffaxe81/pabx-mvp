#!/usr/bin/env python3
"""Diagnóstico somente leitura do Asterisk para homologação do AXE PABX.

Não envia INVITE/REGISTER, não recarrega configuração, não cria canais
e não imprime saída bruta do CLI (pode conter metadados da operação).
Os testes automatizados usam subprocess mockado, sem Docker/Asterisk.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

COMMANDS = {
    "version": "core show version",
    "transports": "pjsip show transports",
    "endpoints": "pjsip show endpoints",
    "dialplan": "dialplan show from-tdm-gateway",
    "channels": "core show channels count",
}
CONTAINER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$")
ENDPOINT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$")
DEFAULT_ENDPOINTS = ("t1-1001", "t2-1001")
MAX_SNAPSHOT_CHARS = 131072
MAX_EXPECTED_ENDPOINTS = 30


def collect_snapshots(runtime="docker", container="pabx-mvp", timeout=8):
    """Executa só os cinco comandos estáticos, sem shell e sem credenciais."""
    if runtime not in {"docker", "local"}:
        raise ValueError("Runtime inválido")
    if runtime == "docker" and not CONTAINER_RE.fullmatch(container):
        raise ValueError("Nome do container inválido")
    snapshots = {}
    for name, command in COMMANDS.items():
        argv = (["docker", "exec", container] if runtime == "docker" else []) + [
            "asterisk", "-rx", command
        ]
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout, check=False
            )
            snapshots[name] = {
                "code": result.returncode,
                "output": result.stdout if result.returncode == 0 else "",
            }
        except (OSError, subprocess.TimeoutExpired):
            snapshots[name] = {"code": None, "output": ""}
    return snapshots


def analyze_snapshots(snapshots, expected_endpoints=DEFAULT_ENDPOINTS):
    """Avalia evidências sem expor saída completa do CLI ou credenciais."""
    if (not isinstance(snapshots, dict)
            or not isinstance(expected_endpoints, (list, tuple))
            or not 1 <= len(expected_endpoints) <= MAX_EXPECTED_ENDPOINTS
            or any(not isinstance(e, str) or not ENDPOINT_RE.fullmatch(e)
                   for e in expected_endpoints)
            or len(set(expected_endpoints)) != len(expected_endpoints)):
        raise ValueError("evidência SIP ou endpoints esperados inválidos")
    checks = {}
    def record(name, ok, description):
        checks[name] = {"ok": bool(ok), "description": description}

    def output(name):
        result = snapshots.get(name, {})
        if (not isinstance(result, dict) or type(result.get("code")) is not int
                or result["code"] != 0):
            return ""
        value = result.get("output")
        return value if isinstance(value, str) and len(value) <= MAX_SNAPSHOT_CHARS else ""

    version = output("version")
    record("asterisk_cli", "Asterisk" in version,
           "CLI local do Asterisk acessível")
    transports = output("transports")
    for name in ("transport-tls", "transport-wss"):
        record(name, bool(re.search(
            r"(?im)^\s*Transport\s*:\s*" + re.escape(name) + r"(?:\s|$)",
            transports)),
               "Transporte PJSIP listado pelo Asterisk")
    endpoints = output("endpoints")
    for name in expected_endpoints:
        registered = bool(re.search(
            r"\b" + re.escape(name) + r"(?:/|\s|$)", endpoints
        ))
        record("endpoint:" + name, registered,
               "Endpoint cadastrado; estado de registro NÃO validado")
    dialplan = output("dialplan")
    record("did_fail_closed", all(fragment in dialplan for fragment in (
        "tenant-did/", "did-desconhecido", "Hangup(21)"
    )), "Dialplan contém lookup e rejeição de DID desconhecido")

    channels = output("channels")
    match = re.search(r"(\d+)\s+active channels?\b", channels, flags=re.I)
    active_channels = int(match.group(1)) if match else None
    record("channels_query", active_channels is not None,
           "Consulta da contagem de canais ativos")
    return {
        "schema_version": 1,
        "kind": "readonly_asterisk_preflight",
        "checks": checks,
        "active_channels": active_channels,
        "ok": all(item["ok"] for item in checks.values()),
        "call_tested": False,
        "rtp_tested": False,
        "tenant_isolation_tested_on_live_calls": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=("docker", "local"), default="docker")
    parser.add_argument("--container", default="pabx-mvp",
                        help="Container Asterisk; usado apenas com --runtime docker")
    parser.add_argument("--expect-endpoint", action="append", dest="endpoints",
                        help="Endpoint esperado (repetir para cada ramal). Padrão t1-1001 e t2-1001.")
    parser.add_argument("--timeout", type=int, default=8)
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 30:
        parser.error("Timeout permitido: 1 a 30 segundos")
    try:
        snapshots = collect_snapshots(args.runtime, args.container, args.timeout)
        report = analyze_snapshots(snapshots, args.endpoints or DEFAULT_ENDPOINTS)
    except ValueError as exc:
        parser.error(str(exc))
    report["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    report["runtime"] = args.runtime
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
