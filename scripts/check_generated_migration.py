#!/usr/bin/env python3
"""Pré-check somente leitura dos arquivos Asterisk após migração de mounts."""
import argparse
import json
from pathlib import Path
import re
import sys

STATIC_FILES = (
    "pjsip_dynamic.conf",
    "extensions_dynamic_dial-t1.conf",
    "extensions_dynamic_hints-t1.conf",
    "voicemail_dynamic_t1.conf",
    "extensions_dynamic_dial-t2.conf",
    "extensions_dynamic_hints-t2.conf",
    "voicemail_dynamic_t2.conf",
)
TENANT_ID = re.compile(r"t[3-9][0-9]*\Z|t[1-9][0-9]{1,}\Z")
STATIC_INCLUDES = {
    "pjsip.conf": ("pjsip_dynamic.conf",),
    "extensions.conf": (
        "extensions_dynamic_dial-t1.conf",
        "extensions_dynamic_hints-t1.conf",
        "extensions_dynamic_dial-t2.conf",
        "extensions_dynamic_hints-t2.conf",
    ),
    "voicemail.conf": (
        "voicemail_dynamic_t1.conf", "voicemail_dynamic_t2.conf",
    ),
}


def read_tenant_registry(path):
    """Use apenas IDs, sem retornar DID ou dados sensíveis."""
    if path is None:
        return []
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("cadastro de tenants ausente ou inseguro")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("cadastro de tenants deve ser lista JSON")
    result = []
    for item in data:
        value = item.get("tenant_id") if isinstance(item, dict) else None
        if not isinstance(value, str) or not TENANT_ID.fullmatch(value):
            raise ValueError("identificador de tenant inválido no cadastro")
        if value in result:
            raise ValueError("tenant duplicado no cadastro")
        result.append(value)
    return result


def inspect(asterisk_dir, registry_path=None, compare_legacy=False):
    root = Path(asterisk_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("diretório Asterisk ausente ou inseguro")
    generated = root / "generated"
    if generated.is_symlink() or not generated.is_dir():
        raise ValueError("diretório generated ausente ou inseguro")
    tenants = read_tenant_registry(registry_path)

    filenames = list(STATIC_FILES)
    for tenant in tenants:
        filenames.extend((
            f"extensions_dynamic_dial-{tenant}.conf",
            f"extensions_dynamic_hints-{tenant}.conf",
            f"voicemail_dynamic_{tenant}.conf",
        ))
    checks = {}
    for name in filenames:
        dest = generated / name
        if dest.is_symlink() or not dest.is_file():
            checks[f"generated:{name}"] = "missing_or_unsafe"
        elif not dest.stat().st_size:
            checks[f"generated:{name}"] = "empty"
        else:
            checks[f"generated:{name}"] = "ok"

        if compare_legacy:
            legacy = root / name
            key = f"legacy_match:{name}"
            if legacy.is_symlink():
                checks[key] = "unsafe_legacy"
            elif legacy.is_file():
                checks[key] = (
                    "ok" if dest.is_file() and not dest.is_symlink()
                    and legacy.read_bytes() == dest.read_bytes()
                    else "different"
                )
            else:
                checks[key] = "no_legacy_file"

    for conf, names in STATIC_INCLUDES.items():
        source = root / conf
        if source.is_symlink() or not source.is_file():
            for name in names:
                checks[f"include:{conf}:{name}"] = "missing_conf"
            continue
        raw = source.read_text(encoding="utf-8")
        for name in names:
            checks[f"include:{conf}:{name}"] = (
                "ok" if re.search(
                    r"(?m)^#include\s+generated/" + re.escape(name) + r"\s*$",
                    raw,
                )
                else "missing_include"
            )

    passed = sum(v in ("ok", "no_legacy_file") for v in checks.values())
    return {
        "schema_version": 1,
        "kind": "host_config_migration_preflight",
        "ready_for_runtime_verification": passed == len(checks),
        "checks_passed": passed,
        "checks_total": len(checks),
        "percent": round(100 * passed / len(checks), 1) if checks else 0,
        "checked_tenants": tenants,
        "compare_legacy": bool(compare_legacy),
        "checks": checks,
        "docker_mount_checked": False,
        "asterisk_reload_checked": False,
        "sip_call_tested": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parent.parent / "asterisk"
    parser.add_argument("--asterisk-dir", default=str(default))
    parser.add_argument("--tenant-registry", help="Opcional: tenants.json do ambiente")
    parser.add_argument("--compare-legacy", action="store_true",
                        help="Usar somente ANTES da migração para conferir cópias")
    args = parser.parse_args(argv)
    try:
        report = inspect(args.asterisk_dir, args.tenant_registry, args.compare_legacy)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Pré-check inválido: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["ready_for_runtime_verification"] else 1


if __name__ == "__main__":
    sys.exit(main())
