"""CLI local de credenciais de filas. Os tokens nunca são versionados.

Emite Bearer de curta duração por empresa/papel. O catálogo é armazenado
atomicamente em volume privado modo 0600, com SHA-256 em vez do token.
"""
import argparse
import hashlib
import json
import os
import secrets
import stat
import time
from pathlib import Path

from queue_access import MAX_QUEUE_CREDENTIALS, load_queue_policy
from recording_access import (
    HEX_SHA256, MAX_POLICY_BYTES, ROLES, TENANT,
    _extension_belongs_to_tenant,
)
from recording_catalog import atomic_save, policy_lock

MIN_TTL = 300
MAX_TTL = 86400


def _validate_catalog_file(path):
    p = Path(path)
    info = p.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("catálogo precisa ser arquivo regular privado (modo 0600)")
    data = load_queue_policy(p)
    if data is None:
        raise ValueError("catálogo inválido")
    return data


def _write(path, policy):
    payload = (json.dumps(policy, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(payload) > MAX_POLICY_BYTES:
        raise ValueError("catálogo excede limite de tamanho")
    atomic_save(path, payload)


def init_policy(path):
    with policy_lock(path):
        if os.path.lexists(path):
            raise ValueError("catálogo já existe; não sobrescrever")
        _write(path, {"credentials": []})
    return {"initialized": True}


def issue_credential(path, tenant, role, extension=None, ttl=3600, now=None):
    if not isinstance(tenant, str) or not TENANT.fullmatch(tenant):
        raise ValueError("empresa inválida")
    if role not in ROLES:
        raise ValueError("papel inválido")
    if type(ttl) is not int or not MIN_TTL <= ttl <= MAX_TTL:
        raise ValueError("TTL deve ser 300..86400 segundos")
    if role == "agent":
        if not _extension_belongs_to_tenant(extension, tenant):
            raise ValueError("agente precisa de ramal da mesma empresa")
    elif extension is not None:
        raise ValueError("extensão só é permitida para agente")
    timestamp = int(time.time() if now is None else now)
    if timestamp < 0:
        raise ValueError("relógio inválido")
    token = secrets.token_urlsafe(48)
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    row = {
        "token_sha256": digest, "tenant": tenant,
        "role": role, "expires_at": timestamp + ttl,
    }
    if extension is not None:
        row["extension"] = extension
    with policy_lock(path):
        data = _validate_catalog_file(path)
        if len(data["credentials"]) >= MAX_QUEUE_CREDENTIALS:
            raise ValueError("limite de credenciais alcançado")
        if any(x["token_sha256"] == digest for x in data["credentials"]):
            raise ValueError("colisão criptográfica inesperada")
        _write(path, {"credentials": [*data["credentials"], row]})
    return {"token": token, "sha256": digest, "tenant": tenant,
            "role": role, "expires_at": row["expires_at"]}


def revoke_credential(path, sha256):
    if not isinstance(sha256, str) or not HEX_SHA256.fullmatch(sha256):
        raise ValueError("hash SHA-256 inválido")
    with policy_lock(path):
        data = _validate_catalog_file(path)
        updated = [r for r in data["credentials"] if r["token_sha256"] != sha256]
        if len(updated) == len(data["credentials"]):
            raise ValueError("credencial não encontrada")
        _write(path, {"credentials": updated})
    return {"revoked": True, "sha256": sha256}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Credenciais locais das filas AXE PABX")
    parser.add_argument("--policy", required=True, help="arquivo em volume privado, fora do Git")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init", help="cria catálogo privado vazio sem sobrescrever")
    issue = subs.add_parser("issue", help="gera token; mostra somente uma vez")
    issue.add_argument("--tenant", required=True)
    issue.add_argument("--role", choices=sorted(ROLES), required=True)
    issue.add_argument("--extension")
    issue.add_argument("--ttl", type=int, default=3600)
    revoke = subs.add_parser("revoke", help="revoga por hash SHA-256")
    revoke.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init_policy(args.policy)
        elif args.command == "issue":
            result = issue_credential(args.policy, args.tenant, args.role,
                                      extension=args.extension, ttl=args.ttl)
        else:
            result = revoke_credential(args.policy, args.sha256)
    except (OSError, ValueError) as exc:
        parser.exit(2, "Operação negada: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
