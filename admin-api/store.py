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
    """
    Valida os campos de um ramal antes de criar/editar. Retorna
    (ok, error_message, cleaned_data).
    """
    name = (data.get("name") or "").strip().lower()
    if not NAME_RE.match(name):
        return False, "nome do ramal deve ter 3-40 caracteres (letras minúsculas, números, hífen)", None

    if any(e["name"] == name for e in existing if e["name"] != editing_name):
        return False, f"já existe um ramal chamado '{name}'", None

    tenant = (data.get("tenant") or DEFAULT_TENANT).strip()
    if tenant not in VALID_TENANTS:
        return False, f"tenant inválido - use um de: {sorted(VALID_TENANTS)}", None

    try:
        number = int(data.get("number"))
    except (TypeError, ValueError):
        return False, "número do ramal inválido", None

    if number not in EXTENSION_NUMBER_RANGE:
        return False, f"número deve estar entre {EXTENSION_NUMBER_RANGE.start} e {EXTENSION_NUMBER_RANGE.stop - 1}", None

    # Números podem repetir ENTRE tenants (contextos isolados) - só
    # precisa ser único dentro do mesmo tenant.
    if any(e["number"] == number and e.get("tenant", DEFAULT_TENANT) == tenant for e in existing if e["name"] != editing_name):
        return False, f"já existe um ramal com o número {number} no tenant {tenant}", None

    display_name = (data.get("display_name") or name).strip()
    if not display_name:
        return False, "nome de exibição obrigatório", None

    password = data.get("password") or secrets.token_urlsafe(12)
    email = (data.get("email") or "").strip()

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
