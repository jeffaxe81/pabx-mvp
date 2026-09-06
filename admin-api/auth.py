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

    salt = bytes.fromhex(salt_hex)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(derived.hex(), hash_hex)


class SessionStore:
    """Sessões em memória - somem se o container reiniciar (ver limitações)."""

    def __init__(self, ttl_seconds=8 * 3600, clock=time.time):
        self._sessions = {}
        self._ttl = ttl_seconds
        self._clock = clock

    def create(self, username: str) -> str:
        token = secrets.token_hex(32)
        self._sessions[token] = {"username": username, "expires_at": self._clock() + self._ttl}
        return token

    def validate(self, token: str):
        """Retorna o username se o token for válido e não expirado, senão None."""
        session = self._sessions.get(token)
        if not session:
            return None
        if self._clock() > session["expires_at"]:
            del self._sessions[token]
            return None
        return session["username"]

    def revoke(self, token: str):
        self._sessions.pop(token, None)
