"""
Autenticação do painel de administração. Lógica pura - sem
dependências externas (nada de bcrypt/argon2 de propósito, pra manter
o projeto sem dependências pip; ver limitação no manual 16 sobre isso
não ser hashing de força de produção).
"""
import hashlib
import hmac
import os
import secrets
import time

PBKDF2_ITERATIONS = 260_000


def hash_password(password: str, salt: bytes = None) -> str:
    """Retorna 'salt_hex:hash_hex'. Gera um salt novo se não informado."""
    salt = salt or os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}:{derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Compara em tempo constante - evita timing attack no login."""
    try:
        salt_hex, hash_hex = stored_hash.split(":")
    except (ValueError, AttributeError):
        return False

    if not isinstance(password, str) or len(salt_hex) != 32 or len(hash_hex) != 64:
        return False
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(derived, expected)


class SessionStore:
    """Sessões em memória - somem se o container reiniciar (ver limitações)."""

    def __init__(self, ttl_seconds=8 * 3600, clock=time.time):
        self._sessions = {}
        self._ttl = ttl_seconds
        self._clock = clock

    def create(self, username: str, role: str = "admin") -> str:
        token = secrets.token_hex(32)
        self._sessions[token] = {"username": username, "role": role, "expires_at": self._clock() + self._ttl}
        return token

    def validate(self, token: str):
        """Retorna o username se o token for válido e não expirado, senão None."""
        if not isinstance(token, str):
            return None
        session = self._sessions.get(token)
        if not session:
            return None
        if self._clock() >= session["expires_at"]:
            del self._sessions[token]
            return None
        return session["username"]

    def get_role(self, token: str):
        """Retorna o papel (role) da sessão, ou None se o token for inválido/expirado."""
        if not isinstance(token, str):
            return None
        session = self._sessions.get(token)
        if not session or self._clock() >= session["expires_at"]:
            return None
        return session["role"]

    def revoke(self, token: str):
        if isinstance(token, str):
            self._sessions.pop(token, None)
