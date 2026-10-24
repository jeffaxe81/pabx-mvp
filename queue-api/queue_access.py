"""Credenciais efêmeras, independentes das gravações, para filas AXE PABX.

Catálogo privado com somente SHA-256 do Bearer, sem credenciais em git
ou em parâmetros URL. Sem arquivo válido, os endpoints falham fechado.
A abertura segura por FD é compartilhada com a proteção de gravações.
"""
import json
import math
import os
import stat

from recording_access import (
    HEX_SHA256, MAX_POLICY_BYTES, ROLES, TENANT,
    _extension_belongs_to_tenant, _open_policy_file,
    authenticate_recordings, allowed_browser_origin,
)

MAX_QUEUE_CREDENTIALS = 256


def load_queue_policy(path):
    """Lê configuração estrita, sem symlinks e com limite de tamanho."""
    fd = _open_policy_file(path)
    if fd is None:
        return None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077
                or info.st_size > MAX_POLICY_BYTES):
            return None
        with os.fdopen(fd, "rb") as opened:
            fd = None
            payload = opened.read(MAX_POLICY_BYTES + 1)
        if len(payload) > MAX_POLICY_BYTES:
            return None
        policy = json.loads(payload)
    except (OSError, TypeError, ValueError, UnicodeError):
        return None
    finally:
        if fd is not None:
            os.close(fd)

    # Outro catálogo (inclusive de gravações) não é aceito por engano.
    if not isinstance(policy, dict) or set(policy) != {"credentials"}:
        return None
    credentials = policy["credentials"]
    if not isinstance(credentials, list) or len(credentials) > MAX_QUEUE_CREDENTIALS:
        return None
    seen = set()
    for credential in credentials:
        if not isinstance(credential, dict):
            return None
        role = credential.get("role")
        tenant = credential.get("tenant")
        digest = credential.get("token_sha256")
        expires = credential.get("expires_at")
        extension = credential.get("extension")
        expected = {"token_sha256", "tenant", "role", "expires_at"}
        if role == "agent":
            expected.add("extension")
        if (
            set(credential) != expected
            or not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest)
            or digest in seen
            or not isinstance(tenant, str) or not TENANT.fullmatch(tenant)
            or role not in ROLES
            or type(expires) not in (int, float) or not math.isfinite(expires)
            or expires <= 0
            or (role == "agent" and not _extension_belongs_to_tenant(extension, tenant))
        ):
            return None
        seen.add(digest)
    return policy


def authenticate_queue(authorization, policy, now=None):
    """Faz validação Bearer e expiração usando a rotina auditada."""
    return authenticate_recordings(authorization, policy, now=now)


def may_pickup(principal, extension):
    """Agente só pode atuar no próprio ramal; supervisor no tenant."""
    if not isinstance(principal, dict) or not isinstance(extension, str):
        return False
    tenant = principal.get("tenant")
    if not isinstance(tenant, str) or not TENANT.fullmatch(tenant):
        return False
    if not _extension_belongs_to_tenant(extension, tenant):
        return False
    role = principal.get("role")
    return (
        role in {"supervisor", "admin"}
        or (role == "agent" and principal.get("extension") == extension)
    )
