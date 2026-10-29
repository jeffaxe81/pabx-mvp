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
SOURCE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{3,99}$")
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

def read_regular_file_secure(path, maximum_bytes):
    """Lê a fonte privada por FD seguro, sem seguir links nos ancestrais.

    O fstat se refere ao próprio arquivo aberto, e não a um caminho que
    possa ser trocado entre lstat e read_bytes. Nenhum arquivo especial
    é lido, e não há fallback permissivo.
    """
    if type(maximum_bytes) is not int or maximum_bytes <= 0:
        raise ValueError("limite de leitura inválido")
    fd = _open_policy_file(path)
    if fd is None:
        raise ValueError("fonte não é arquivo regular seguro")
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum_bytes:
            raise ValueError("fonte não é arquivo regular ou excede o limite")
        with os.fdopen(fd, "rb") as opened:
            fd = None
            content = opened.read(maximum_bytes + 1)
        if len(content) > maximum_bytes:
            raise ValueError("fonte excede o limite")
        return content
    finally:
        if fd is not None:
            os.close(fd)


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("chave JSON duplicada na política de gravações")
        result[key] = value
    return result


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
        policy = json.loads(raw, object_pairs_hook=_reject_duplicate_json_keys,
                            parse_constant=lambda value: (_ for _ in ()).throw(
                                ValueError("constante JSON não finita")))
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
    source_tenants = {}
    for filename, metadata in policy["recordings"].items():
        if not _valid_filename(filename) or not isinstance(metadata, dict):
            return None
        tenant = metadata.get("tenant")
        if not isinstance(tenant, str) or not TENANT.fullmatch(tenant):
            return None
        source_ref = metadata.get("source_ref")
        if source_ref is not None:
            if not isinstance(source_ref, str) or not SOURCE_REF.fullmatch(source_ref):
                return None
            # A mesma prova CDR/AMI não pode atestar duas empresas.
            previous = source_tenants.setdefault(source_ref, tenant)
            if previous != tenant:
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
    # A leitura normal valida o catálogo, mas um chamador pode passar uma
    # estrutura adulterada diretamente em memória. Não autorizar credenciais
    # nem lançar exceção quando o estado estiver inconsistente.
    credentials = policy.get("credentials")
    if not isinstance(credentials, list):
        return None
    current = time.time() if now is None else now
    if type(current) not in (int, float) or not math.isfinite(current):
        return None
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    seen = set()
    matching = None
    for cred in credentials:
        if not isinstance(cred, dict):
            return None
        stored = cred.get("token_sha256")
        tenant, role = cred.get("tenant"), cred.get("role")
        expiry = cred.get("expires_at")
        if (
            not isinstance(stored, str) or not HEX_SHA256.fullmatch(stored)
            or stored in seen
            or not isinstance(tenant, str) or not TENANT.fullmatch(tenant)
            or not isinstance(role, str) or role not in ROLES
        ):
            return None
        if type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry <= 0:
            return None
        if role == "agent":
            if not _extension_belongs_to_tenant(cred.get("extension"), tenant):
                return None
        elif cred.get("extension") is not None:
            return None
        seen.add(stored)
        if hmac.compare_digest(digest, stored) and current < expiry:
            matching = cred
    return matching


def can_read_recording(policy, principal, filename):
    if not isinstance(policy, dict) or not isinstance(principal, dict):
        return False
    if not _valid_filename(filename):
        return False
    catalog = policy.get("recordings")
    if not isinstance(catalog, dict):
        return False
    metadata = catalog.get(filename)
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
    if not isinstance(role, str):
        return False
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
    if not isinstance(origins, (set, frozenset, list, tuple)):
        return False
    return origin in origins
