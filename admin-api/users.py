"""
Usuários do painel de administração, com papéis (backlog #19):
- admin: acesso total (ramais, lista de bloqueio, modo feriado, outros usuários)
- supervisor: só leitura de ramais/bloqueio, mas pode alternar o modo
  feriado (é operacional, não destrutivo)

Lógica pura de validação/armazenamento aqui - hashing de senha fica em
auth.py (reaproveitado, não duplicado).
"""
import json
import re
from pathlib import Path

from auth import hash_password

ROLES = {"admin", "supervisor"}
USERNAME_RE = re.compile(r"^[a-z0-9_-]{3,30}$")


def load_users(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_users(path, users: list):
    Path(path).write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")


def find_user(users: list, username: str):
    return next((u for u in users if u["username"] == username), None)


def validate_user_input(data: dict, existing: list, editing_username: str = None):
    """
    Valida os campos de um usuário do painel. Retorna
    (ok, error_message, cleaned_data). Se 'password' vier vazio numa
    edição, mantém o hash antigo (não força trocar senha pra editar
    outra coisa, tipo o papel).
    """
    username = (data.get("username") or "").strip().lower()
    if not USERNAME_RE.match(username):
        return False, "usuário deve ter 3-30 caracteres (letras minúsculas, números, hífen, underscore)", None

    if any(u["username"] == username for u in existing if u["username"] != editing_username):
        return False, f"já existe um usuário chamado '{username}'", None

    role = data.get("role", "")
    if role not in ROLES:
        return False, f"papel inválido - use um de: {', '.join(sorted(ROLES))}", None

    password = data.get("password") or ""
    if password:
        password_hash = hash_password(password)
    elif editing_username:
        existing_user = find_user(existing, editing_username)
        password_hash = existing_user["password_hash"]
    else:
        return False, "senha obrigatória para novo usuário", None

    return True, None, {
        "username": username,
        "password_hash": password_hash,
        "role": role,
        # Campos de 2FA (backlog #20) - None/False pra usuário novo;
        # em edição, 'data' já vem mesclado com os valores atuais (ver
        # update_user), então .get() aqui preserva o que já existia.
        "totp_secret": data.get("totp_secret"),
        "totp_enabled": bool(data.get("totp_enabled", False)),
    }


def add_user(path, data: dict):
    existing = load_users(path)
    ok, error, cleaned = validate_user_input(data, existing)
    if not ok:
        return False, error, None

    existing.append(cleaned)
    save_users(path, existing)
    return True, None, cleaned


def update_user(path, username: str, data: dict):
    existing = load_users(path)
    if not find_user(existing, username):
        return False, f"usuário '{username}' não encontrado", None

    merged = {**find_user(existing, username), **data, "username": username}
    ok, error, cleaned = validate_user_input(merged, existing, editing_username=username)
    if not ok:
        return False, error, None

    updated = [cleaned if u["username"] == username else u for u in existing]
    save_users(path, updated)
    return True, None, cleaned


def delete_user(path, username: str):
    existing = load_users(path)
    filtered = [u for u in existing if u["username"] != username]
    if len(filtered) == len(existing):
        return False, f"usuário '{username}' não encontrado"
    if not any(u["role"] == "admin" for u in filtered):
        return False, "não é possível remover o último usuário administrador"

    save_users(path, filtered)
    return True, None


def public_user(user: dict) -> dict:
    """Remove o hash de senha e o segredo TOTP antes de mandar pro navegador."""
    return {k: v for k, v in user.items() if k not in ("password_hash", "totp_secret")}
