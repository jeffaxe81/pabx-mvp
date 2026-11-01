#!/usr/bin/env python3
"""Validação não destrutiva de um arquivo de rollback antes da extração."""
import argparse
import pathlib
import sys
import tarfile

REQUIRED = (
    "pabx/asterisk/",
    "pabx/admin/",
    "pabx/webphone/",
    "pabx/provisioning/",
    "pabx/recordings/",
    "pabx/docker-compose.yml",
    "pabx/prompt-base-pabx.md",
)


def validate(path):
    seen = set()
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            parts = pathlib.PurePosixPath(name).parts
            if not parts or parts[0] != "pabx" or ".." in parts:
                raise ValueError("caminho inseguro no backup")
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise ValueError("tipo de entrada inseguro no backup")
            if not (member.isfile() or member.isdir()):
                raise ValueError("tipo de entrada não suportado")
            seen.add(name.rstrip("/"))
    for required in REQUIRED:
        if required.rstrip("/") not in seen:
            raise ValueError(f"entrada obrigatória ausente: {required}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    args = parser.parse_args()
    try:
        validate(args.archive)
    except (ValueError, OSError, tarfile.TarError) as exc:
        print(f"ERRO: backup inválido para restauração: {exc}", file=sys.stderr)
        sys.exit(2)
    print("OK: backup íntegro na leitura e estrutura mínima validada; restauração não executada")
