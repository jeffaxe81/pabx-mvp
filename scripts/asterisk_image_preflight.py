#!/usr/bin/env python3
"""Preflight de imagem Asterisk imutável, sem Docker, rede ou deploy.

O digest do docker-compose deve coincidir EXATAMENTE com o da imagem
utilizada no laboratório real do mesmo checkout. Isto comprova apenas
identidade de imagem declarada, não compatibilidade no host alvo.
"""
import argparse
import ast
from pathlib import Path
import re
import sys

IMAGE_RE = re.compile(
    r"andrius/asterisk:[A-Za-z0-9][A-Za-z0-9_.-]*@sha256:[0-9a-f]{64}\Z"
)
MAX_FILE_SIZE = 1024 * 1024


def read_text(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("arquivo ausente, simbólico ou grande demais")
    return p.read_text(encoding="utf-8")


def lab_image(source):
    """Extrai a constante IMAGE via AST, sem executar/importar o laboratório."""
    tree = ast.parse(source)
    values = [
        node.value for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "IMAGE"
    ]
    if len(values) != 1:
        raise ValueError("constante IMAGE do laboratório ausente ou duplicada")
    try:
        value = ast.literal_eval(values[0])
    except (TypeError, ValueError, SyntaxError, RecursionError):
        raise ValueError("constante IMAGE do laboratório não é literal") from None
    if not isinstance(value, str):
        raise ValueError("constante IMAGE deve ser texto")
    return value


def compose_asterisk_image(source):
    """Parser mínimo e restritivo para o bloco canônico do serviço Asterisk.

    Não tenta interpretar YAML genérico: se o layout mudar, falha fechado.
    Os testes completos da CI validam o YAML via PyYAML separadamente.
    """
    if not isinstance(source, str) or len(source) > MAX_FILE_SIZE:
        raise ValueError("compose inválido")
    services = False
    asterisk = False
    seen_service = 0
    images = []
    for line in source.splitlines():
        if line == "services:":
            services = True
            continue
        if re.fullmatch(r"[^\s#][^:]*:", line):
            services = False
            asterisk = False
            continue
        service = re.fullmatch(r"  ([a-z][a-z0-9-]*):(?:\s+#.*)?", line)
        if services and service:
            asterisk = service.group(1) == "asterisk"
            if asterisk:
                seen_service += 1
            continue
        if services and asterisk and re.match(r"^    image\s*:", line):
            match = re.fullmatch(r"    image:\s*([^\s#]+)\s*(?:#.*)?", line)
            if not match:
                raise ValueError("referência de imagem Asterisk ambígua")
            images.append(match.group(1))
    if seen_service != 1 or len(images) != 1:
        raise ValueError("bloco Asterisk ou referência de imagem ausente/duplicada")
    return images[0]


def inspect(root):
    root = Path(root)
    try:
        compose = compose_asterisk_image(read_text(root / "docker-compose.yml"))
        lab = lab_image(read_text(root / "lab/asterisk_lab.py"))
    except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
        return {"ok": False, "reason": "arquivo ou formato de configuração inválido"}
    if ":latest@" in compose or ":latest@" in lab:
        return {"ok": False, "reason": "tag latest mutável não permitida para RC operacional"}
    if not IMAGE_RE.fullmatch(compose) or not IMAGE_RE.fullmatch(lab):
        return {"ok": False, "reason": "imagem sem tag versionada e digest sha256 fixo"}
    if compose != lab:
        return {"ok": False, "reason": "imagem do compose diverge da imagem de CI"}
    return {"ok": True, "reason": "digest do Asterisk declarado coincide com CI"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    result = inspect(args.root)
    print(("OK: " if result["ok"] else "BLOQUEIO: ") + result["reason"])
    print("Produção permanece NO-GO; validar segredos, certificados e compatibilidade no host.")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
