#!/usr/bin/env python3
"""Preflight local, somente leitura, de TLS SIP, credenciais e permissões.

Valida a configuração da árvore fornecida, não substitui testes em Asterisk real.
Nunca imprime segredos nem conteúdo de chaves/certificados.
"""
import argparse
import os
from pathlib import Path
import re
import sys

DEFAULT_SECRET = re.compile(
    r"^(?:troque_esta_senha(?:[_-].*)?|changeme|password|admin)$", re.I
)
ASSIGNMENT = re.compile(
    r"^\s*(?:-\s*)?(?:password|secret|AMI_SECRET)\s*[:=]\s*(.*?)\s*$",
    re.I,
)
TLS_BLOCK = "transport-tls"
CONFIG_FILES = ("asterisk/pjsip.conf", "asterisk/manager.conf", "docker-compose.yml")


def _value(raw):
    """Remove aspas e comentários usuais sem revelar o valor ao operador."""
    value = raw.strip()
    if value.startswith(('"', "'")):
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end >= 0 else value[1:]
    return re.split(r"\s+[;#]", value, maxsplit=1)[0].strip()


def _tls_options(content):
    """Extrai apenas a seção [transport-tls]; não aceita texto em comentários."""
    in_section = False
    values = {}
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "#")):
            continue
        section = re.fullmatch(r"\[([^\]]+)\]", line)
        if section:
            in_section = section.group(1).lower() == TLS_BLOCK
            continue
        if in_section and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip().lower()] = _value(value).lower() if key.strip().lower() in (
                "type", "protocol", "method"
            ) else _value(value)
    return values


def _sensitive_permissions(path, relative, findings):
    if os.name != "posix" or not path.exists():
        return
    try:
        if path.is_symlink():
            findings.append(f"{relative}: link simbólico não permitido para segredo")
        elif path.stat().st_mode & 0o077:
            findings.append(f"{relative}: permissões de grupo/outros sobre arquivo sensível")
    except OSError:
        findings.append(f"{relative}: permissões não verificáveis")


def inspect(root):
    root = Path(root)
    findings = []
    for relative in CONFIG_FILES:
        path = root / relative
        if not path.is_file():
            findings.append(f"{relative}: arquivo ausente")
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("#", ";")):
                continue
            match = ASSIGNMENT.match(line)
            if match and DEFAULT_SECRET.fullmatch(_value(match.group(1))):
                findings.append(f"{relative}:{number}: credencial padrão (valor omitido)")

    pjsip = root / "asterisk/pjsip.conf"
    if pjsip.is_file():
        opts = _tls_options(pjsip.read_text(encoding="utf-8"))
        if (opts.get("type") != "transport" or opts.get("protocol") != "tls"
                or opts.get("method") not in ("tlsv1_2", "tlsv1_3")):
            findings.append("asterisk/pjsip.conf: transporte TLS SIP mínimo não comprovado")
        for field in ("cert_file", "priv_key_file"):
            value = opts.get(field)
            if not value or not value.startswith("/etc/asterisk/certs/"):
                findings.append(f"asterisk/pjsip.conf: {field} não configurado em /etc/asterisk/certs/")
                continue
            name = value.removeprefix("/etc/asterisk/certs/")
            if not name or "/" in name or name in (".", ".."):
                findings.append(f"asterisk/pjsip.conf: {field} com caminho inesperado")
                continue
            relative = f"asterisk/certs/{name}"
            local = root / relative
            if not local.is_file():
                findings.append(f"{relative}: material TLS ausente no host analisado")
            if field == "priv_key_file":
                _sensitive_permissions(local, relative, findings)

    _sensitive_permissions(root / "asterisk/manager.conf", "asterisk/manager.conf", findings)
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
    print("OK: configuração local sem bloqueios estáticos encontrados; testes operacionais ainda necessários")
    return 0


if __name__ == "__main__":
    sys.exit(main())
