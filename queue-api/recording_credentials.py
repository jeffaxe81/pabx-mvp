"""Gerência local de credenciais temporárias de gravações, sem SSO.

Execute apenas em console privado no servidor com acesso ao catálogo
modo 0600. Nunca registrar o token em versionamento ou logs.
"""
import argparse
import hashlib
import json
import re
import secrets
import time

from recording_access import HEX_SHA256, MAX_POLICY_BYTES, ROLES, TENANT
from recording_catalog import EXTENSION, atomic_save, policy_lock, read_policy_secure

MAX_CREDENTIALS = 256
MIN_TTL = 300
MAX_TTL = 86400


def _encode(policy):
    encoded = (json.dumps(policy, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(encoded) > MAX_POLICY_BYTES:
        raise ValueError("tamanho máximo de política excedido")
    return encoded


def issue_credential(policy_path, tenant, role, extension=None, ttl=3600, now=None):
    if not isinstance(tenant, str) or not TENANT.fullmatch(tenant):
        raise ValueError("tenant inválido")
    if not isinstance(role, str) or role not in ROLES:
        raise ValueError("papel inválido")
    if type(ttl) is not int or not MIN_TTL <= ttl <= MAX_TTL:
        raise ValueError("TTL deve estar entre 300 e 86400 segundos")
    if role == "agent":
        if (
            not isinstance(extension, str) or not EXTENSION.fullmatch(extension)
            or not extension.startswith(tenant + "-")
        ):
            raise ValueError("agente requer ramal pertencente ao tenant")
    elif extension is not None:
        raise ValueError("somente agente pode receber extensão associada")
    issued = int(time.time() if now is None else now)
    if issued < 0:
        raise ValueError("relógio inválido")
    token = secrets.token_urlsafe(48)
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    entry = {
        "token_sha256": digest, "tenant": tenant, "role": role,
        "expires_at": issued + ttl,
    }
    if extension is not None:
        entry["extension"] = extension

    with policy_lock(policy_path):
        policy = read_policy_secure(policy_path)
        creds = list(policy["credentials"])
        if len(creds) >= MAX_CREDENTIALS:
            raise ValueError("limite de credenciais atingido")
        if any(item["token_sha256"] == digest for item in creds):
            raise ValueError("colisão de digest; repita a emissão")
        policy["credentials"] = [*creds, entry]
        atomic_save(policy_path, _encode(policy))
    return {"token": token, "sha256": digest, "tenant": tenant,
            "role": role, "expires_at": issued + ttl}


def revoke_credential(policy_path, digest):
    if not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
        raise ValueError("hash SHA-256 inválido")
    with policy_lock(policy_path):
        policy = read_policy_secure(policy_path)
        before = len(policy["credentials"])
        policy["credentials"] = [
            item for item in policy["credentials"]
            if item["token_sha256"] != digest
        ]
        if len(policy["credentials"]) == before:
            raise ValueError("credencial não encontrada")
        atomic_save(policy_path, _encode(policy))
    return {"revoked": True, "sha256": digest}


def list_credential_metadata(policy_path):
    policy = read_policy_secure(policy_path)
    return [
        {
            "sha256": entry["token_sha256"], "tenant": entry["tenant"],
            "role": entry["role"], "expires_at": entry["expires_at"],
            **({"extension": entry["extension"]} if "extension" in entry else {}),
        }
        for entry in policy["credentials"]
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Administrar Bearer de gravações no servidor local")
    parser.add_argument("--policy", required=True)
    actions = parser.add_subparsers(dest="command", required=True)
    issue = actions.add_parser("issue", help="gera token novo de curta duração")
    issue.add_argument("--tenant", required=True)
    issue.add_argument("--role", required=True, choices=sorted(ROLES))
    issue.add_argument("--extension")
    issue.add_argument("--ttl", type=int, default=3600)
    revoke = actions.add_parser("revoke", help="revoga imediatamente uma credencial")
    revoke.add_argument("--sha256", required=True)
    actions.add_parser("list", help="lista apenas metadados, nunca tokens")
    args = parser.parse_args(argv)
    try:
        if args.command == "issue":
            result = issue_credential(
                args.policy, args.tenant, args.role, args.extension, args.ttl,
            )
        elif args.command == "revoke":
            result = revoke_credential(args.policy, args.sha256)
        else:
            result = {"credentials": list_credential_metadata(args.policy)}
    except (OSError, ValueError) as exc:
        parser.exit(2, "Operação negada: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
