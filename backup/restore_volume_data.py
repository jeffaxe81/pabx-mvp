#!/usr/bin/env python3
"""Restaura dados dos dois volumes em diretórios offline, sem Docker/socket.

Uso: python3 backup/restore_volume_data.py ARQUIVO.tar.gz DEST_ADMIN DEST_QUEUE
Os diretórios de destino devem existir, ser vazios e não podem ser symlinks.
O operador é responsável por parar os serviços antes da execução.
"""
import argparse
import pathlib
import shutil
import sys
import tarfile

try:
    from validate_archive import validate
except ImportError:
    from backup.validate_archive import validate

VOLUMES = ("admin_data", "queue_api_data")


def restore(archive_path, admin_dest, queue_dest):
    validate(archive_path)
    destinations = (pathlib.Path(admin_dest), pathlib.Path(queue_dest))
    for destination in destinations:
        if destination.is_symlink() or not destination.is_dir() or any(destination.iterdir()):
            raise ValueError("destino deve ser diretório existente, vazio e não simbólico")
    if destinations[0].resolve() == destinations[1].resolve():
        raise ValueError("destinos devem ser diferentes")
    with tarfile.open(archive_path, "r:gz") as archive:
        for name, destination in zip(VOLUMES, destinations):
            prefix = f"pabx/{name}/"
            for member in archive.getmembers():
                if not member.name.startswith(prefix) or member.isdir():
                    continue
                relative = pathlib.PurePosixPath(member.name[len(prefix):])
                if not relative.parts or ".." in relative.parts:
                    raise ValueError("caminho inseguro")
                target = destination.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("entrada não legível")
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    parser.add_argument("admin_dest")
    parser.add_argument("queue_dest")
    args = parser.parse_args()
    try:
        restore(args.archive, args.admin_dest, args.queue_dest)
    except (OSError, ValueError, tarfile.TarError) as exc:
        print(f"ERRO: restauração offline não concluída: {exc}", file=sys.stderr)
        return 2
    print("OK: dados de ambos os volumes recuperados offline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
