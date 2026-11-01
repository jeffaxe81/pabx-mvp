#!/usr/bin/env python3
"""Verificação fechada da release candidate local. Não autoriza produção."""
import argparse
from pathlib import Path
import re
import sys

TAG_RE = re.compile(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)-rc\.[1-9][0-9]*\Z")
CHECK = re.compile(r"^- \[([ x])\] \*\*REL-(\d{2}) — .+$")
REQUIRED_RELEASE_WORDS = (
    "GO operacional: BLOQUEADO",
    "Sem implantação em produção",
    "REL-13",
    "REL-14",
    "REL-20",
    "Revisão humana obrigatória",
    "v0.1.0-rc.1",
)


def inspect(root):
    root = Path(root)
    errors = []
    try:
        version = (root / "RELEASE_VERSION").read_text(encoding="utf-8").strip()
        checklist = (root / "docs/release-fechamento-20-entregas.md").read_text(encoding="utf-8")
        acceptance = (root / "docs/rel20-release-candidate.md").read_text(encoding="utf-8")
    except OSError:
        return None, ["artefato obrigatório ausente"]
    if not TAG_RE.fullmatch(version):
        errors.append("versão RC sem formato semântico permitido")
    found = [CHECK.fullmatch(line) for line in checklist.splitlines() if line.startswith("- [")]
    if len(found) != 20 or any(match is None for match in found):
        errors.append("checklist incompleto ou malformado")
    else:
        ids = [int(match.group(2)) for match in found]
        if ids != list(range(1, 21)):
            errors.append("IDs REL-01..REL-20 ausentes, duplicados ou fora de ordem")
        if any(match.group(1) != "x" for match in found):
            errors.append("ainda existem entregas pendentes")
    if ("20/20 concluídas (100%)" not in checklist
            or "100% (20/20)" not in checklist):
        errors.append("percentual oficial de fechamento inconsistente")
    if not all(item in acceptance for item in REQUIRED_RELEASE_WORDS):
        errors.append("termo de aceite incompleto ou sem limites de produção")
    if version not in acceptance or "tag automática na main" not in acceptance:
        errors.append("documentação da tag/versão incompleta")
    return version, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    version, errors = inspect(args.root)
    if errors:
        for error in errors:
            print("REL-20 BLOQUEADA: " + error, file=sys.stderr)
        return 2
    print(f"REL-20 RC pronta: {version}; checklist=20/20; produção NÃO autorizada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
