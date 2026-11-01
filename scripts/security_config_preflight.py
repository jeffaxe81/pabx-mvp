#!/usr/bin/env python3
"""Preflight local de segurança, sem alterar arquivos nem segredos."""
import argparse
from pathlib import Path
import re
import sys

DEFAULT_SECRET = re.compile(r"^(?:troque_esta_senha|changeme|password|admin)(?:[_-].*)?$", re.I)
SENSITIVE = re.compile(r"^\s*(?:password|secret|AMI_SECRET)\s*[:=]\s*[\"']?([^\"'\s#;]+)", re.I)


def inspect(root):
    root = Path(root)
    findings = []
    for relative in ("asterisk/pjsip.conf", "asterisk/manager.conf", "docker-compose.yml"):
        path = root / relative
        if not path.is_file():
            findings.append(f"{relative}: arquivo ausente")
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("#", ";")):
                continue
            match = SENSITIVE.match(line)
            if match and DEFAULT_SECRET.fullmatch(match.group(1)):
                findings.append(f"{relative}:{number}: credencial padrão (valor omitido)")
    pjsip = root / "asterisk/pjsip.conf"
    if pjsip.is_file():
        data = pjsip.read_text(encoding="utf-8")
        if "method=tlsv1_2" not in data:
            findings.append("asterisk/pjsip.conf: TLS 1.2 não configurado")
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    findings = inspect(args.root)
    for finding in findings:
        print("BLOQUEIO: " + finding)
    if findings:
        return 2
    print("OK: nenhuma credencial padrão reconhecida; TLS SIP mínimo verificado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
