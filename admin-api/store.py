"""
CRUD de ramais gerenciados pelo painel de administração. Guarda tudo
num JSON simples (extensions_store.json) - sem banco de dados de
propósito, consistente com o resto do projeto (poucas dependências,
fácil de inspecionar o estado inteiro abrindo um arquivo).

MVP: só ramais do tenant 1 (ver manual 16 pra limitação e caminho de
extensão pra multi-tenant).
"""
import json
import re
import secrets
from pathlib import Path

EXTENSION_NUMBER_RANGE = range(1100, 1200)  # faixa reservada pro painel
NAME_RE = re.compile(r"^[a-z0-9-]{3,40}$")

# Multi-tenant (backlog #38) - mesma lista de tenants conhecidos do
# server.py (duplicada aqui de propósito, mesmo padrão de pequenas
# duplicações já usado no projeto pra manter cada módulo independente
# - ver ami_protocol.py compartilhado entre admin-api/queue-api).
VALID_TENANTS = {"t1", "t2"}
DEFAULT_TENANT = "t1"


def load_store(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_store(path, extensions: list):
    Path(path).write_text(json.dumps(extensions, indent=2, ensure_ascii=False), encoding="utf-8")


def validate_extension_input(data: dict, existing: list, editing_name: str = None):
    """Rejeita JSON de tipos incorretos e valores que quebram .conf."""
    if not isinstance(data, dict):
        return False, "dados do ramal devem ser um objeto JSON", None
    if not isinstance(existing, list) or any(
        not isinstance(e, dict)
        or not isinstance(e.get("name"), str)
        or not isinstance(e.get("number"), (int, str))
        or (e.get("tenant") is not None and not isinstance(e["tenant"], str))
        for e in existing
    ):
        return False, "cadastro de ramais existente é inválido", None

    raw_name = data.get("name")
    if not isinstance(raw_name, str):
        return False, "nome do ramal deve ser texto", None
    name = raw_name.strip().lower()
    if not NAME_RE.fullmatch(name) or "\r" in raw_name or "\n" in raw_name:
        return False, "nome do ramal deve ter 3-40 caracteres (letras minúsculas, números, hífen)", None
    if any(e["name"] == name for e in existing if e["name"] != editing_name):
        return False, f"já existe um ramal chamado '{name}'", None

    raw_tenant = data.get("tenant", DEFAULT_TENANT)
    if raw_tenant is None:
        raw_tenant = DEFAULT_TENANT
    if not isinstance(raw_tenant, str):
        return False, "tenant deve ser texto", None
    tenant = raw_tenant.strip()
    if tenant not in VALID_TENANTS:
        return False, f"tenant inválido - use um de: {sorted(VALID_TENANTS)}", None

    raw_number = data.get("number")
    if isinstance(raw_number, bool) or not (
        isinstance(raw_number, int)
        or (isinstance(raw_number, str) and raw_number.isascii()
            and raw_number.isdecimal())
    ):
        return False, "número do ramal inválido", None
    try:
        number = int(raw_number)
    except (TypeError, ValueError):
        return False, "número do ramal inválido", None
    if number not in EXTENSION_NUMBER_RANGE:
        return False, f"número deve estar entre {EXTENSION_NUMBER_RANGE.start} e {EXTENSION_NUMBER_RANGE.stop - 1}", None

    # Números repetidos são permitidos em tenants diferentes.
    if any(
        int(e["number"]) == number and e.get("tenant", DEFAULT_TENANT) == tenant
        for e in existing if e["name"] != editing_name
    ):
        return False, f"já existe um ramal com o número {number} no tenant {tenant}", None

    raw_display = data.get("display_name")
    if raw_display is None or raw_display == "":
        raw_display = name
    if not isinstance(raw_display, str):
        return False, "nome de exibição deve ser texto", None
    display_name = raw_display.strip()
    if not 1 <= len(display_name) <= 60 or not display_name.isprintable() or any(
        ch in ";=,<>[]" for ch in display_name
    ):
        return False, "nome de exibição inválido (1-60 caracteres, sem delimitadores de configuração)", None

    raw_password = data.get("password")
    if raw_password is None or raw_password == "":
        password = secrets.token_urlsafe(24)
    elif not isinstance(raw_password, str):
        return False, "senha SIP deve ser texto", None
    elif not 12 <= len(raw_password) <= 128 or not re.fullmatch(
        r"[A-Za-z0-9._~!@#$%^&*()+\-=]{12,128}", raw_password
    ):
        return False, "senha SIP deve ter 12-128 caracteres sem espaços ou delimitadores inseguros", None
    else:
        password = raw_password

    raw_email = data.get("email")
    if raw_email is None or raw_email == "":
        email = ""
    elif not isinstance(raw_email, str):
        return False, "e-mail deve ser texto", None
    else:
        email = raw_email.strip()
        if len(email) > 254 or not re.fullmatch(
            r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}", email
        ):
            return False, "e-mail inválido para configuração de voicemail", None

    return True, None, {
        "name": name,
        "number": number,
        "display_name": display_name,
        "password": password,
        "email": email,
        "tenant": tenant,
    }


def add_extension(path, data: dict):
    existing = load_store(path)
    ok, error, cleaned = validate_extension_input(data, existing)
    if not ok:
        return False, error, None

    existing.append(cleaned)
    save_store(path, existing)
    return True, None, cleaned


def update_extension(path, name: str, data: dict):
    existing = load_store(path)
    if not any(e["name"] == name for e in existing):
        return False, f"ramal '{name}' não encontrado", None

    merged = {**next(e for e in existing if e["name"] == name), **data, "name": name}
    ok, error, cleaned = validate_extension_input(merged, existing, editing_name=name)
    if not ok:
        return False, error, None

    updated = [cleaned if e["name"] == name else e for e in existing]
    save_store(path, updated)
    return True, None, cleaned


def delete_extension(path, name: str):
    existing = load_store(path)
    filtered = [e for e in existing if e["name"] != name]
    if len(filtered) == len(existing):
        return False, f"ramal '{name}' não encontrado"

    save_store(path, filtered)
    return True, None


def delete_extensions_by_tenant(path, tenant_id: str) -> int:
    """
    Remove TODOS os ramais dinâmicos de um tenant de uma vez (backlog
    #54) - usado quando o tenant inteiro é removido pelo wizard
    (manual 39/52), pra não deixar ramal órfão apontando pra um
    contexto que não existe mais. Retorna quantos foram removidos.
    """
    existing = load_store(path)
    remaining = [e for e in existing if e.get("tenant", DEFAULT_TENANT) != tenant_id]
    removed_count = len(existing) - len(remaining)
    if removed_count:
        save_store(path, remaining)
    return removed_count
