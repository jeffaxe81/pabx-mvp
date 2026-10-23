#!/usr/bin/env python3
"""Auditoria somente leitura de Asterisk *em execução* no laboratório.

Executa comandos CLI allowlisted, sem shell e sem ações de escrita.
Não origina chamadas, não realiza REGISTER nem valida RTP/SRTP.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

from sip_preflight import CONTAINER_RE

TENANT_RE = re.compile(r"t[1-9][0-9]*\Z")
DID_RE = re.compile(r"[0-9]{8,15}\Z")
STATIC_ENDPOINTS = {"t1": "t1-1001", "t2": "t2-1001"}
MAX_TENANTS = 30
MAX_RESULT_CHARS = 131072

BASE_COMMANDS = {
    "version": "core show version",
    "transports": "pjsip show transports",
    "ingress": "dialplan show from-tdm-gateway",
    "astdb": "database show tenant-did",
}


def read_expected_tenants(path):
    """Obtém expectativas do catálogo local privado sem expor DIDs no relatório."""
    if path is None:
        return {}
    registry = Path(path)
    if registry.is_symlink() or not registry.is_file():
        raise ValueError("registro de tenants ausente ou inseguro")
    data = json.loads(registry.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) > MAX_TENANTS:
        raise ValueError("registro de tenants inválido ou excessivo")
    tenants = {}
    dids = set()
    for row in data:
        if not isinstance(row, dict):
            raise ValueError("registro de tenants contém item inválido")
        tid, did = row.get("tenant_id"), row.get("did")
        if not isinstance(tid, str) or not TENANT_RE.fullmatch(tid) or tid in ("t1", "t2"):
            raise ValueError("ID de tenant inválido")
        if not isinstance(did, str) or not DID_RE.fullmatch(did):
            raise ValueError("DID inválido no catálogo")
        if tid in tenants or did in dids:
            raise ValueError("tenant ou DID duplicado no catálogo")
        tenants[tid] = did
        dids.add(did)
    return tenants


def planned_commands(expected):
    """Nenhum comando contém dados de entrada livres ou credenciais."""
    commands = dict(BASE_COMMANDS)
    for tid in ("t1", "t2", *sorted(expected)):
        endpoint = STATIC_ENDPOINTS.get(tid, f"{tid}-recepcao")
        commands[f"endpoint:{tid}"] = f"pjsip show endpoint {endpoint}"
        commands[f"context:{tid}"] = f"dialplan show {tid}-internal"
    return commands


def run_cli(commands, *, runtime="docker", container="pabx-mvp", timeout=8):
    if runtime not in ("docker", "local"):
        raise ValueError("runtime inválido")
    if runtime == "docker" and not CONTAINER_RE.fullmatch(container):
        raise ValueError("nome do container inválido")
    if not isinstance(timeout, int) or not 1 <= timeout <= 30:
        raise ValueError("timeout inválido")
    outputs = {}
    for key, command in commands.items():
        if command not in planned_commands({}).values():
            # Permite comandos de t3+ somente se gerados pelo planejador:
            if not re.fullmatch(r"pjsip show endpoint t(?:[3-9]|[1-9][0-9]+)-recepcao", command) and not re.fullmatch(
                r"dialplan show t(?:[3-9]|[1-9][0-9]+)-internal", command
            ):
                raise ValueError("comando não permitido")
        argv = (["docker", "exec", container] if runtime == "docker" else []) + [
            "asterisk", "-rx", command
        ]
        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, check=False, timeout=timeout,
            )
            stdout = completed.stdout or ""
            outputs[key] = {
                "code": completed.returncode,
                "output": stdout[:MAX_RESULT_CHARS],
                "truncated": len(stdout) > MAX_RESULT_CHARS,
            }
        except (OSError, subprocess.TimeoutExpired, UnicodeError):
            outputs[key] = {"code": None, "output": "", "truncated": False}
    return outputs


def _healthy_output(snapshots, name):
    entry = snapshots.get(name, {})
    if entry.get("code") != 0 or entry.get("truncated"):
        return ""
    return entry.get("output", "")


def check_snapshots(snapshots, expected):
    """Exige contexto por tenant; nunca copia CLI ou DID para o resultado."""
    checks = {}
    def check(name, condition):
        checks[name] = bool(condition)

    version = _healthy_output(snapshots, "version")
    check("runtime_version", bool(re.search(r"\bAsterisk\b", version, re.I)))
    transports = _healthy_output(snapshots, "transports")
    for transport in ("transport-tls", "transport-wss"):
        check(f"transport:{transport}",
              bool(re.search(r"\b" + re.escape(transport) + r"\b", transports)))
    ingress = _healthy_output(snapshots, "ingress")
    check("ingress_unknown_did_rejection", all(
        x in ingress for x in ("tenant-did/", "did-desconhecido", "Hangup(21)")
    ))

    for tid in ("t1", "t2", *sorted(expected)):
        endpoint = STATIC_ENDPOINTS.get(tid, f"{tid}-recepcao")
        output = _healthy_output(snapshots, f"endpoint:{tid}")
        listed = bool(re.search(
            r"(?im)^\s*Endpoint\s*:\s*" + re.escape(endpoint) + r"(?:/|\s|$)", output
        ))
        # Asterisk PJSIP exibe opções como "context : t1-internal"
        # (muitas versões usam minúsculas e espaço antes de ':').
        # Exigir a linha da opção, não aceitar apenas texto avulso.
        context_matches = bool(re.search(
            r"(?im)^\s*context\s*:\s*" + re.escape(f"{tid}-internal") + r"(?:\s|$)",
            output
        ))
        check(f"endpoint_exists:{tid}", listed)
        check(f"endpoint_context:{tid}", listed and context_matches)
        dialplan = _healthy_output(snapshots, f"context:{tid}")
        check(f"dialplan_context:{tid}", bool(re.search(
            r"\[\s*Context\s+['\"]" + re.escape(f"{tid}-internal") + r"['\"]", dialplan, re.I
        )))

    # Asterisk database show pode listar vários DIDs. A saída não
    # aparece no JSON final: somente uma confirmação por tenant.
    astdb = _healthy_output(snapshots, "astdb")
    for tid, did in sorted(expected.items()):
        entries = [
            (number, owner) for number, owner in re.findall(
                r"(?m)^\s*/tenant-did/([0-9]{8,15})\s*:\s*(t[1-9][0-9]*)\s*$", astdb
            ) if number == did
        ]
        check(f"did_mapping:{tid}", entries == [(did, tid)])

    passed = sum(checks.values())
    return {
        "schema_version": 1,
        "kind": "running_asterisk_readonly_lab_audit",
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "percent": round(100 * passed / len(checks), 1),
        "ready_for_call_homologation": passed == len(checks),
        "dynamic_tenants_checked": sorted(expected),
        "registration_verified": False,
        "sip_call_tested": False,
        "rtp_tested": False,
        "srtp_tested": False,
        "live_tenant_isolation_tested": False,
        "backup_restore_tested": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=["docker", "local"], default="docker")
    parser.add_argument("--container", default="pabx-mvp")
    parser.add_argument("--tenant-registry", help="Arquivo tenants.json privado para verificar t3+")
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--source-commit", help="SHA de 40 caracteres do release implantado (declarado pelo operador)")
    args = parser.parse_args(argv)
    if args.source_commit is not None and not re.fullmatch(r"[0-9a-fA-F]{40}", args.source_commit):
        parser.error("source-commit deve ser SHA Git completo de 40 caracteres")
    try:
        expected = read_expected_tenants(args.tenant_registry)
        commands = planned_commands(expected)
        snaps = run_cli(commands, runtime=args.runtime, container=args.container,
                        timeout=args.timeout)
        report = check_snapshots(snaps, expected)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(f"auditoria inválida: {type(exc).__name__}")
    report["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    report["runtime"] = args.runtime
    report["source_commit"] = args.source_commit.lower() if args.source_commit else None
    report["source_commit_verified_by_this_tool"] = False
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["ready_for_call_homologation"] else 1


if __name__ == "__main__":
    sys.exit(main())
