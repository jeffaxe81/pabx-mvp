#!/usr/bin/env python3
"""Ensaio OFFLINE de rollback integral, exclusivamente em sandbox com marcador.

Não acessa Docker, rede, SIP ou arquivos do PABX operacional.
Para restauração do host real, usar restore.sh + procedimento dos volumes.
"""
import argparse
import pathlib
import shutil
import sys
import tarfile
import tempfile

from validate_archive import validate

DIRECTORIES = (
    "asterisk", "admin", "webphone", "provisioning",
    "recordings", "admin_data", "queue_api_data",
)
FILES = ("docker-compose.yml", "prompt-base-pabx.md")
ENTRIES = DIRECTORIES + FILES
MARKER = ".axe-pabx-sandbox"


def _remove(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def restore_sandbox(archive_path, target_path):
    target = pathlib.Path(target_path)
    if target.is_symlink() or not target.is_dir() or target.resolve() == pathlib.Path("/"):
        raise ValueError("destino inválido: somente diretório sandbox explícito")
    if not (target / MARKER).is_file() or (target / MARKER).is_symlink():
        raise ValueError("marcador de sandbox obrigatório; host real é proibido")
    # Validar antes de qualquer alteração, bloqueando links e paths inseguros.
    validate(archive_path)
    with tempfile.TemporaryDirectory(prefix="axe-rel17-", dir=target.parent) as temporary:
        staging = pathlib.Path(temporary)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(path=staging, filter="data")
        restored = staging / "pabx"
        for entry in DIRECTORIES:
            if not (restored / entry).is_dir():
                raise ValueError("diretório ausente no snapshot: " + entry)
        for entry in FILES:
            if not (restored / entry).is_file():
                raise ValueError("arquivo ausente no snapshot: " + entry)
        previous = staging / "previous"
        previous.mkdir()
        done = []
        try:
            # Diretórios completos, não cópia por sobreposição: remove órfãos
            # deixados pela versão nova. Inclui as imagens locais dos volumes.
            for entry in ENTRIES:
                source = restored / entry
                destination = target / entry
                old = previous / entry
                had_old = destination.exists() or destination.is_symlink()
                if had_old:
                    destination.rename(old)
                try:
                    source.rename(destination)
                except Exception:
                    if had_old:
                        old.rename(destination)
                    raise
                done.append((destination, old, had_old))
        except Exception:
            # Retornar todos os componentes já trocados se um passo falhar.
            for destination, old, had_old in reversed(done):
                _remove(destination)
                if had_old:
                    old.rename(destination)
            raise
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument("--sandbox-root", required=True)
    args = parser.parse_args(argv)
    try:
        restore_sandbox(args.archive, args.sandbox_root)
    except (ValueError, OSError, tarfile.TarError) as exc:
        print("REL-17: rollback sandbox recusado: " + str(exc), file=sys.stderr)
        return 2
    print("REL-17: rollback integral do snapshot em sandbox OK (sem Docker/SIP)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
