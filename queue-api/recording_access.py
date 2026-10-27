"""
Política independente de acesso a gravações do AXE PABX.

Nunca inferir o tenant a partir do nome do áudio (há nomes legados
ambíguos). Um catálogo administrativo liga cada arquivo ao tenant
com evidência da origem. Sem política/registro válido, negar acesso.
"""
import hashlib
import hmac
import json
import math
import os
import re
import stat
import time
from pathlib import Path
from urllib.parse import urlsplit

HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
TENANT = re.compile(r"^t[1-9][0-9]*$")
TENANT_EXTENSION = re.compile(r"^t[1-9][0-9]*-[a-z0-9][a-z0-9_-]{0,79}$")
ROLES = {"admin", "supervisor", "agent"}
EXTENSIONS = {".wav", ".gsm", ".mp3"}
MAX_POLICY_BYTES = 1024 * 1024
_OPEN_SUPPORTS_DIR_FD = hasattr(os, "supports_dir_fd") and os.open in os.supports_dir_fd


def _valid_filename(filename):
    return (
        isinstance(filename, str) and 1 <= len(filename) <= 240
        and "/" not in filename and "\\" not in filename
        and filename not in {".", ".."}
        and all(ord(c) >= 32 and ord(c) != 127 for c in filename)
        and Path(filename).suffix.lower() in EXTENSIONS
    )


def _extension_belongs_to_tenant(extension, tenant):
    """Verifica identidade exata; prefixo t1 nao pode aceitar t10 nem t2."""
    return (
        isinstance(extension, str)
        and isinstance(tenant, str)
        and TENANT_EXTENSION.fullmatch(extension) is not None
        and extension.startswith(tenant + "-")
    )



def _open_policy_file(path):
    """Abre o catálogo ancorando CADA ancestral em FD de diretório.

    O_NOFOLLOW no arquivo isolado não protege componentes parent
    intermediários. Atravessar com openat(dir_fd=...) impede que um
    symlink inserido em qualquer nível redirecione a leitura.
    """
    required = ("O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY")
    if (not all(hasattr(os, name) for name in required)
            or not _OPEN_SUPPORTS_DIR_FD):
        return None
    directory_fd = None
    try:
        candidate = Path(path)
        parts = candidate.parts
        if candidate.is_absolute():
            if not parts or parts[0] != "/":
                return None
            anchor, components = "/", parts[1:]
        else:
            anchor, components = ".", parts
        if not components or any(part in {"", ".", ".."} for part in components):
            return None
        directory_fd = os.open(anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for component in components[:-1]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY |
                              os.O_NOFOLLOW, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        return os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW |
                       os.O_NONBLOCK, dir_fd=directory_fd)
    except (OSError, TypeError, ValueError, NotImplementedError):
        return None
    finally:
        if directory_fd is not None:
            os.close(directory_fd)

def load_recording_policy(path):
    """Devolve None para ausente, JSON inválido ou esquema inseguro."""
    # Abertura relativa a diretórios ancorados evita a troca do arquivo
    # ou de QUALQUER pasta ancestral por symlink durante a leitura.
    fd = _open_policy_file(path)
    if fd is None:
        return None
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_POLICY_BYTES:
            return None
        with os.fdopen(fd, "rb") as opened:
            fd = None
            raw = opened.read(MAX_POLICY_BYTES + 1)
        if len(raw) > MAX_POLICY_BYTES:
            return None
        policy = json.loads(raw)
    except (OSError, ValueError, TypeError, UnicodeError):
        return None
    finally:
        if fd is not None:
            os.close(fd)
    if not isinstance(policy, dict) or not isinstance(policy.get("credentials"), list):
        return None
    if not isinstance(policy.get("recordings"), dict):
        return None
    seen = set()
    for cred in policy["credentials"]:
        if not isinstance(cred, dict):
            return None
        digest, tenant, role = cred.get("token_sha256"), cred.get("tenant"), cred.get("role")
        expiry = cred.get("expires_at")
        if (
            not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest)
            or digest in seen or not isinstance(tenant, str) or not TENANT.fullmatch(tenant)
            or not isinstance(role, str) or role not in ROLES
            or type(expiry) not in (int, float)
            or not math.isfinite(expiry) or expiry <= 0
        ):
            return None
        seen.add(digest)
        if role == "agent":
            if not _extension_belongs_to_tenant(cred.get("extension"), tenant):
                return None
        elif cred.get("extension") is not None:
            return None
    for filename, metadata in policy["recordings"].items():
        if not _valid_filename(filename) or not isinstance(metadata, dict):
            return None
        tenant = metadata.get("tenant")
        if not isinstance(tenant, str) or not TENANT.fullmatch(tenant):
            return None
        owner = metadata.get("owner_extension")
        if owner is not None and not _extension_belongs_to_tenant(owner, tenant):
            return None
    return policy


def authenticate_recordings(authorization, policy, now=None):
    """Bearer de alta entropia; armazenar APENAS o SHA-256 no catálogo."""
    if not isinstance(policy, dict) or not isinstance(authorization, str):
        return None
    prefix, separator, token = authorization.partition(" ")
    if not separator or prefix.lower() != "bearer":
        return None
    if not (32 <= len(token) <= 256) or not token.isascii() or not token.isprintable() or " " in token:
        return None
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    current = time.time() if now is None else now
    for cred in policy["credentials"]:
        if hmac.compare_digest(digest, cred["token_sha256"]) and current < cred["expires_at"]:
            return cred
    return None


def can_read_recording(policy, principal, filename):
    if not isinstance(policy, dict) or not isinstance(principal, dict):
        return False
    if not _valid_filename(filename):
        return False
    metadata = policy["recordings"].get(filename)
    tenant = principal.get("tenant")
    if (
        not isinstance(metadata, dict)
        or not isinstance(tenant, str)
        or TENANT.fullmatch(tenant) is None
        or tenant != metadata.get("tenant")
    ):
        return False
    owner = metadata.get("owner_extension")
    if owner is not None and not _extension_belongs_to_tenant(owner, tenant):
        return False
    role = principal.get("role")
    if role in {"admin", "supervisor"}:
        return True
    return (
        role == "agent"
        and _extension_belongs_to_tenant(principal.get("extension"), tenant)
        and owner == principal.get("extension")
    )


def allowed_browser_origin(origin, origins):
    """Sem wildcard, prefix match, sufixo de domínio ou reflexão livre."""
    if not isinstance(origin, str) or not origin:
        return False
    try:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment
            or origin == "null"
        ):
            return False
    except ValueError:
        return False
    return origin in origins
