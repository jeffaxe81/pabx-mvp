#!/usr/bin/env python3
"""Auditoria fail-closed das configuracoes versionadas (NAO testa chamadas reais).

Somente pjsip.conf, queues.conf, voicemail.conf e extensions.conf base.
Includes dinamicos, AstDB, API, SIP, midia e runtime exigem aceites separados.
A saida omite linhas de configuracao, senhas, DIDs e audio.
"""
import argparse
import json
from pathlib import Path
import re

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "asterisk"
REQUIRED_FILES = ("pjsip.conf", "queues.conf", "voicemail.conf", "extensions.conf")
TENANT = r"t[1-9][0-9]*"
SECTION = re.compile(r"^\[([A-Za-z0-9_-]+)\](?:\(([^)]*)\))?$")
TENANT_ENDPOINT = re.compile(rf"^({TENANT})-[A-Za-z0-9_-]+$")
TENANT_CONTEXT = re.compile(rf"^({TENANT})-internal$")
TENANT_QUEUE = re.compile(rf"^fila-({TENANT})(?:-[a-z]+)?$")
TENANT_VM = re.compile(rf"^({TENANT})$")
# Checa apenas referencias LITERAIS; interpolacoes de variaveis nao sao prova.
REFERENCES = re.compile(
    rf"PJSIP/({TENANT})-|@({TENANT})\b|\bfila-({TENANT})\b|"
    rf"\bGoto\(({TENANT})-internal\b|CDR\(accountcode\)\s*=\s*({TENANT})\b",
    re.IGNORECASE,
)


def parse_configuration(path):
    """Secoes preservam entradas repetidas (member => ...) e contexto de templates."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("unsafe or missing configuration")
    entries = []
    current = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "#")):
            continue
        line = line.split(";", 1)[0].strip()
        match = SECTION.fullmatch(line)
        if match:
            current = {"name": match.group(1), "template": match.group(2) or "",
                       "items": [], "lines": []}
            entries.append(current)
        elif current is not None:
            current["lines"].append(line)
            if "=>" in line:
                k, v = line.split("=>", 1)
                current["items"].append((k.strip().lower(), v.strip()))
            elif "=" in line:
                k, v = line.split("=", 1)
                current["items"].append((k.strip().lower(), v.strip()))
    return entries


def values(section, key):
    return [v for k, v in section["items"] if k == key]


def singleton(section, key, expected):
    return values(section, key) == [expected]


def audit(root=DEFAULT_ROOT):
    root = Path(root)
    checks = {}
    try:
        data = {name: parse_configuration(root / name) for name in REQUIRED_FILES}
    except (OSError, UnicodeError, ValueError):
        data = {}
    checks["files_readable_and_safe"] = len(data) == len(REQUIRED_FILES)
    if not checks["files_readable_and_safe"]:
        return report(checks, [])
    pjsip, queues, vm, dial = (data[name] for name in REQUIRED_FILES)
    endpoints = []
    for section in pjsip:
        found = TENANT_ENDPOINT.fullmatch(section["name"])
        if found and ("endpoint" in section["template"] or
                      values(section, "type") == ["endpoint"]):
            endpoints.append((found.group(1), section))
    tenants = {"t1", "t2"}
    tenants.update(tid for tid, _ in endpoints)
    tenants.update(m.group(1) for s in queues if (m := TENANT_QUEUE.fullmatch(s["name"])))
    tenants.update(m.group(1) for s in vm if (m := TENANT_VM.fullmatch(s["name"])))
    tenants.update(m.group(1) for s in dial if (m := TENANT_CONTEXT.fullmatch(s["name"])))
    for tid in sorted(tenants, key=lambda x: int(x[1:])):
        names = [s for s in dial if s["name"] == tid + "-internal"]
        checks["dialplan_context:" + tid] = len(names) == 1
        checks["has_pjsip_endpoint:" + tid] = any(t == tid for t, _ in endpoints)
        q = [s for s in queues if s["name"] == "fila-" + tid]
        checks["has_primary_queue:" + tid] = len(q) == 1 and bool(values(q[0], "member"))
        mail = [s for s in vm if s["name"] == tid]
        checks["has_voicemail_context:" + tid] = len(mail) == 1
        for _, ep in [item for item in endpoints if item[0] == tid]:
            key = ep["name"]
            checks["context:" + key] = singleton(ep, "context", tid + "-internal")
            checks["subscribe:" + key] = singleton(ep, "subscribe_context", tid + "-hints")
            checks["auth:" + key] = singleton(ep, "auth", key)
            checks["aors:" + key] = singleton(ep, "aors", key)
            boxes = values(ep, "mailboxes")
            checks["mailboxes:" + key] = len(boxes) == 1 and all(
                box.startswith(tid + "-") and box.endswith("@" + tid)
                for box in boxes[0].split(",")
            )
        for section in (s for s in queues if TENANT_QUEUE.fullmatch(s["name"]) and
                        TENANT_QUEUE.fullmatch(s["name"]).group(1) == tid):
            members = values(section, "member")
            checks["members:" + section["name"]] = bool(members) and all(
                re.fullmatch(rf"PJSIP/{tid}-[A-Za-z0-9_-]+(?:,[0-9]+)?", member)
                for member in members
            )
        if len(mail) == 1:
            box_ids = [k for k, _ in mail[0]["items"] if k != "include"]
            checks["voicemail_boxes:" + tid] = bool(box_ids) and all(
                box.startswith(tid + "-") for box in box_ids
            )
        if len(names) == 1:
            foreign = [
                match for line in names[0]["lines"]
                for found in REFERENCES.finditer(line)
                if (match := next((g for g in found.groups() if g), None)) != tid
            ]
            checks["dialplan_literal_refs:" + tid] = not foreign
    return report(checks, sorted(tenants, key=lambda x: int(x[1:])))


def report(checks, tenants):
    passed = sum(value is True for value in checks.values())
    return {
        "success": passed == len(checks),
        "passed": passed,
        "total": len(checks),
        "failed_checks": sorted(key for key, value in checks.items() if value is not True),
        "tenants_in_versioned_config": tenants,
        "scope": "versioned_static_base_configs_only",
        "generated_includes_evaluated": False,
        "astdb_and_api_tested": False,
        "live_tenant_isolation_tested": False,
        "sip_rtp_tested": False,
        "operational_go_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asterisk-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    result = audit(args.asterisk_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
