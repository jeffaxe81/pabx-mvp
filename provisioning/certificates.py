"""Inventario e revogacao LOCAL de certificados mTLS de laboratorio.

Nao emite certificados, nao publica portas e nao autoriza producao.
Execute a partir da raiz: python -m provisioning.certificates --help
"""
import argparse
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import secrets
import stat
import sys
import time

from provisioning import mtls_server as pv


def _tenant(value):
    if not isinstance(value, str) or not pv.TENANT_RE.fullmatch(value):
        raise ValueError("tenant invalido")


def list_certificates(registry_path, devices_path, tenant=None, *, now=None):
    """Somente metadados: nunca hash, certificado, chave ou senha SIP."""
    if tenant is not None:
        _tenant(tenant)
    moment = time.time() if now is None else now
    try:
        valid_clock = type(moment) in (int, float) and math.isfinite(moment) and moment > 0
    except OverflowError:
        valid_clock = False
    if not valid_clock:
        raise ValueError("relogio invalido")
    registry = pv.read_json(registry_path, private=True)
    pv.validate_policy(registry, pv.read_json(devices_path))
    rows = []
    for entry in registry["devices"]:
        if tenant is not None and entry["tenant"] != tenant:
            continue
        if entry["revoked"]:
            state = "revoked"
        elif moment < entry["valid_from"]:
            state = "pending"
        elif moment >= entry["valid_until"]:
            state = "expired"
        else:
            state = "active"
        rows.append({field: entry[field] for field in
                     ("tenant", "mac", "valid_from", "valid_until")})
        rows[-1]["status"] = state
    return sorted(rows, key=lambda row: (row["tenant"], row["mac"]))


@contextmanager
def _locked_registry(path):
    """Lock estavel em diretorio privado; todos os escritores devem usa-lo."""
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("operacao requer Linux/POSIX")
    import fcntl
    path = Path(path)
    if not path.name:
        raise ValueError("caminho de cadastro invalido")
    root_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        root = os.fstat(root_fd)
        if root.st_mode & 0o077 or root.st_uid != os.geteuid():
            raise ValueError("diretorio do cadastro deve ser privado e do operador")
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
        lock_fd = os.open(path.name + ".lock", flags, 0o600, dir_fd=root_fd)
        try:
            lock = os.fstat(lock_fd)
            if (not stat.S_ISREG(lock.st_mode) or lock.st_mode & 0o077
                    or lock.st_uid != os.geteuid() or lock.st_nlink != 1):
                raise ValueError("lock privado invalido")
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                registry = pv.read_json(path.name, private=True, dir_fd=root_fd)
                yield registry, root_fd, path.name
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)
    finally:
        os.close(root_fd)


def _atomic_save(root_fd, name, registry):
    # Nao inflar um cadastro valido perto de MAX_JSON so pela formatacao.
    content = (json.dumps(registry, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False) + "\n").encode("utf-8")
    if len(content) > pv.MAX_JSON:
        raise ValueError("JSON excede limite")
    temporary = "." + name + "." + secrets.token_hex(12) + ".tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=root_fd)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            os.fchmod(fd, 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(fd)
        os.replace(temporary, name, src_dir_fd=root_fd, dst_dir_fd=root_fd)
        # Depois da publicacao, falha de fsync nao deve desfazer a revogacao.
        os.fsync(root_fd)
    finally:
        os.close(fd)
        try:
            os.unlink(temporary, dir_fd=root_fd)
        except FileNotFoundError:
            pass


def revoke_certificate(registry_path, devices_path, tenant, mac):
    """Revoga somente o par exato; repetir uma revogacao nao regrava o JSON."""
    _tenant(tenant)
    if not isinstance(mac, str) or not pv.MAC_RE.fullmatch(mac):
        raise ValueError("MAC invalido")
    with _locked_registry(registry_path) as (registry, root_fd, name):
        devices = pv.read_json(devices_path)
        pv.validate_policy(registry, devices)
        entry = next((row for row in registry["devices"]
                      if row["tenant"] == tenant and row["mac"] == mac), None)
        if entry is None:
            raise ValueError("vinculo nao encontrado")
        changed = not entry["revoked"]
        if changed:
            entry["revoked"] = True
            pv.validate_policy(registry, devices)
            _atomic_save(root_fd, name, registry)
    return {"tenant": tenant, "mac": mac, "revoked": True, "changed": changed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--devices", type=Path, required=True)
    actions = parser.add_subparsers(dest="command", required=True)
    inventory = actions.add_parser("list", help="somente metadados e estado de validade")
    inventory.add_argument("--tenant")
    revoke = actions.add_parser("revoke", help="revogacao exata por tenant e MAC")
    revoke.add_argument("--tenant", required=True)
    revoke.add_argument("--mac", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            result = {"devices": list_certificates(args.registry, args.devices, args.tenant)}
        else:
            result = revoke_certificate(args.registry, args.devices, args.tenant, args.mac)
    except (ValueError, OSError, OverflowError) as exc:
        # A mensagem original pode conter caminho, JSON ou detalhes privados.
        print("Operacao de certificados bloqueada: " + type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
