#!/usr/bin/env python3
"""Auditoria offline de PINs do voicemail. Somente contagens; nunca publica PINs.

Verifica configurações explícitas fornecidas pelo operador, inclusive
arquivos dinâmicos se passados. Não acessa mensagens nem Asterisk.
"""
import argparse
import json
import re
from pathlib import Path

TENANT = re.compile(r"t[1-9][0-9]*\Z")
MAILBOX = re.compile(r"t[1-9][0-9]*-[a-z0-9][a-z0-9_-]*\Z")
COMMON = {"12345678", "87654321", "11111111", "00000000", "99999999"}


def audit_voicemail_text(content, seen_pins=None):
    """Reprova PIN fraco, contexto órfão e mailbox em tenant divergente.

    Não inclui PIN, nome de mailbox ou linha de origem no resultado.
    """
    result = {"mailboxes": 0, "weak_pins": 0, "reused_pins": 0,
              "cross_tenant": 0, "malformed": 0, "tenants": set()}
    seen = set() if seen_pins is None else seen_pins
    if not isinstance(content, str) or len(content) > 1024 * 1024:
        return None
    context = None
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                result["malformed"] += 1
                context = None
            else:
                context = line[1:-1].strip()
            continue
        if "=>" not in line:
            continue
        mailbox, fields = (value.strip() for value in line.split("=>", 1))
        if not MAILBOX.fullmatch(mailbox):
            result["malformed"] += 1
            continue
        result["mailboxes"] += 1
        if context is None or not TENANT.fullmatch(context) or not mailbox.startswith(context + "-"):
            result["cross_tenant"] += 1
        else:
            result["tenants"].add(context)
        pin = fields.split(",", 1)[0].strip()
        if pin in seen:
            result["reused_pins"] += 1
        seen.add(pin)
        # O painel gera 8 dígitos; padrões conhecidos ou comprimento curto
        # não atendem ao aceite. Nunca divulgar o valor.
        if (not pin.isascii() or not pin.isdecimal() or len(pin) < 8
                or pin in COMMON or len(set(pin)) < 3):
            result["weak_pins"] += 1
    result["tenants"] = sorted(result["tenants"])
    result["ok"] = (
        result["mailboxes"] > 0
        and result["weak_pins"] == 0
        and result["reused_pins"] == 0
        and result["cross_tenant"] == 0
        and result["malformed"] == 0
    )
    return result


def audit_voicemail_files(paths):
    """Recusa arquivo ausente, diretório, symlink ou excessivo sem retornar bytes."""
    combined = {"mailboxes": 0, "weak_pins": 0, "reused_pins": 0,
                "cross_tenant": 0, "malformed": 0, "tenants": set()}
    seen = set()
    if not paths:
        return {"ok": False, "error": "no_inputs"}
    for supplied in paths:
        try:
            path = Path(supplied)
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
                return {"ok": False, "error": "invalid_input"}
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError, TypeError, ValueError):
            return {"ok": False, "error": "unreadable_input"}
        item = audit_voicemail_text(content, seen)
        if item is None:
            return {"ok": False, "error": "oversized_input"}
        for key in ("mailboxes", "weak_pins", "reused_pins", "cross_tenant", "malformed"):
            combined[key] += item[key]
        combined["tenants"].update(item["tenants"])
    combined["tenants"] = sorted(combined["tenants"])
    combined["ok"] = (
        combined["mailboxes"] > 0
        and all(combined[k] == 0 for k in ("weak_pins", "reused_pins", "cross_tenant", "malformed"))
    )
    combined["files_checked"] = len(paths)
    return combined


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="voicemail.conf e arquivos gerados no ambiente local")
    args = parser.parse_args(argv)
    result = audit_voicemail_files(args.files)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
