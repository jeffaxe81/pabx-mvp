"""
TOTP (Time-based One-Time Password, RFC 6238) - o mesmo algoritmo do
Google Authenticator, Authy, etc. Implementado com biblioteca padrão
do Python (hmac/hashlib/base64/struct) de propósito, consistente com
a política de zero dependências externas do resto do projeto.

Lógica 100% pura - nenhuma função aqui depende de rede, tempo real
(o timestamp é sempre injetável) ou I/O.
"""
import base64
import hashlib
import hmac
import os
import struct
import time
import urllib.parse

DEFAULT_STEP_SECONDS = 30
DEFAULT_DIGITS = 6


def generate_secret(length_bytes: int = 20) -> str:
    """Gera um segredo aleatório em Base32 (formato padrão pra apps autenticadores)."""
    return base64.b32encode(os.urandom(length_bytes)).decode("ascii").rstrip("=")


def _hotp(secret_b32: str, counter: int, digits: int = DEFAULT_DIGITS) -> str:
    """HOTP (RFC 4226) - a base do TOTP, usando o contador em vez do tempo direto."""
    padding = "=" * ((8 - len(secret_b32) % 8) % 8)
    key = base64.b32decode(secret_b32.upper() + padding)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code_int).zfill(digits)


def generate_totp(secret_b32: str, timestamp: float = None, step: int = DEFAULT_STEP_SECONDS, digits: int = DEFAULT_DIGITS) -> str:
    """Gera o código de 6 dígitos válido pro instante dado (ou agora, se omitido)."""
    ts = timestamp if timestamp is not None else time.time()
    counter = int(ts // step)
    return _hotp(secret_b32, counter, digits)


def verify_totp(secret_b32: str, code: str, timestamp: float = None, step: int = DEFAULT_STEP_SECONDS, window: int = 1) -> bool:
    """
    Verifica um código, tolerando +-`window` períodos de 30s pra
    absorver diferença de relógio entre o celular e o servidor.
    """
    if not secret_b32 or not code:
        return False

    ts = timestamp if timestamp is not None else time.time()
    counter = int(ts // step)
    code = code.strip()

    for offset in range(-window, window + 1):
        try:
            if _hotp(secret_b32, counter + offset, DEFAULT_DIGITS) == code:
                return True
        except Exception:  # noqa: BLE001 - segredo malformado não deve derrubar o login
            return False
    return False


def build_provisioning_uri(secret_b32: str, username: str, issuer: str = "PABX Admin") -> str:
    """
    URI otpauth:// padrão, reconhecida por Google Authenticator, Authy,
    1Password, etc. - dá pra colar direto num app que aceite import por
    texto/link (sem gerar QR code de imagem, ver manual 26).
    """
    label = urllib.parse.quote(f"{issuer}:{username}")
    query = urllib.parse.urlencode({"secret": secret_b32, "issuer": issuer, "algorithm": "SHA1", "digits": DEFAULT_DIGITS, "period": DEFAULT_STEP_SECONDS})
    return f"otpauth://totp/{label}?{query}"
