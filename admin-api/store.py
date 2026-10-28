"""
CRUD de ramais gerenciados pelo painel de administração. Guarda tudo
num JSON simples (extensions_store.json) - sem banco de dados de
propósito, consistente com o resto do projeto (poucas dependências,
fácil de inspecionar o estado inteiro abrindo um arquivo).

Por padrão, as chamadas legadas continuam limitadas a t1/t2. O
servidor passa explicitamente os tenants habilitados pelo wizard.
"""
import json
import os
import re
import secrets
import tempfile
import threading
from pathlib import Path

EXTENSION_NUMBER_RANGE = range(1100, 1200)  # faixa reservada pro painel
NAME_RE = re.compile(r"^[a-z0-9-]{3,40}$")

# Multi-tenant (backlog #38) - mesma lista de tenants conhecidos do
# server.py (duplicada aqui de propósito, mesmo padrão de pequenas
# duplicações já usado no projeto pra manter cada módulo independente
# - ver ami_protocol.py compartilhado entre admin-api/queue-api).
VALID_TENANTS = {"t1", "t2"}
DEFAULT_TENANT = "t1"

# O admin-api usa ThreadingHTTPServer: CRUD precisa serializar a
# sequência carregar -> validar -> salvar, e não apenas o replace.
_STORE_LOCK = threading.RLock()


def load_store(path) -> list:
    """Lê snapshot completo; nunca troca cadastro inválido por vazio."""
    with _STORE_LOCK:
        path = Path(path)
        if path.is_symlink():
            raise ValueError("arquivo de ramais não pode ser link simbólico")
        if not path.exists():
            return []
        if not path.is_file():
            raise ValueError("arquivo de ramais não é regular")
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError("arquivo de ramais precisa conter uma lista JSON")
        return loaded


def save_store(path, extensions: list):
    """Persiste JSON num arquivo temporário privado e publica via replace.

    Em falha de escrita, o snapshot anterior permanece intacto.
    A sincronização entre múltiplos processos/hosts requer trava externa.
    """
    with _STORE_LOCK:
        if not isinstance(extensions, list):
            raise ValueError("cadastro de ramais deve ser uma lista")
        target = Path(path)
        if target.is_symlink():
            raise ValueError("arquivo de ramais não pode ser link simbólico")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent,
                prefix=f".{target.name}.", delete=False
            ) as handle:
                temporary = Path(handle.name)
                os.chmod(temporary, 0o600)
                json.dump(extensions, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


def validate_extension_input(data: dict, existing: list, editing_name: str = None, allowed_tenants=None):
    """Rejeita JSON de tipos incorretos e valores que quebram .conf."""
    if not isinstance(data, dict):
        return False, "dados do ramal devem ser um objeto JSON", None
    if not isinstance(existing, list) or any(
        not isinstance(e, dict)
        or not isinstance(e.get("name"), str)
        or isinstance(e.get("number"), bool)
        or not (
            isinstance(e.get("number"), int)
            or (isinstance(e.get("number"), str) and e["number"].isascii()
                and e["number"].isdecimal())
        )
        or (e.get("tenant") is not None and not isinstance(e["tenant"], str))
        or (e.get("voicemail_pin") is not None and not isinstance(e["voicemail_pin"], str))
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
    tenants = VALID_TENANTS if allowed_tenants is None else allowed_tenants
    if not isinstance(tenants, (set, frozenset, list, tuple)) or any(
        not isinstance(t, str) or not re.fullmatch(r"t[1-9][0-9]*", t)
        for t in tenants
    ):
        return False, "registro de tenants disponíveis inválido", None
    if tenant not in tenants:
        return False, f"tenant inválido - use um de: {sorted(tenants)}", None

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
    elif not re.fullmatch(r"[A-Za-z0-9._~!@#$%^&*()+\-=]{1,128}", raw_password):
        return False, "senha SIP contém delimitadores ou caracteres inválidos", None
    elif len(raw_password) < 12 and not (
        editing_name is not None and any(
            e["name"] == editing_name and e.get("password") == raw_password
            for e in existing
        )
    ):
        return False, "senha SIP deve ter pelo menos 12 caracteres", None
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

    # O PIN de voicemail não pode ser escolhido por JSON externo.
    # Cadastro legado sem PIN forte exige rotação administrada explícita;
    # nunca atribuir uma senha previsível ao atualizar o ramal.
    if editing_name is None:
        if "voicemail_pin" in data:
            return False, "PIN de voicemail gerado somente pelo servidor", None
        old_pins = {
            e.get("voicemail_pin") for e in existing
            if e.get("tenant", DEFAULT_TENANT) == tenant
        }
        voicemail_pin = ""
        for _ in range(20):
            candidate = str(secrets.randbelow(90_000_000) + 10_000_000)
            if candidate not in old_pins:
                voicemail_pin = candidate
                break
        if not voicemail_pin:
            return False, "não foi possível gerar PIN de voicemail", None
    else:
        previous = next((e for e in existing if e["name"] == editing_name), None)
        voicemail_pin = previous.get("voicemail_pin") if previous else None
        if not isinstance(voicemail_pin, str) or not re.fullmatch(r"[1-9][0-9]{7}", voicemail_pin):
            return False, "ramal legado requer migração autorizada do PIN de voicemail", None

    return True, None, {
        "name": name,
        "number": number,
        "display_name": display_name,
        "password": password,
        "email": email,
        "tenant": tenant,
        "voicemail_pin": voicemail_pin,
    }


def add_extension(path, data: dict, allowed_tenants=None):
    with _STORE_LOCK:
        existing = load_store(path)
        ok, error, cleaned = validate_extension_input(data, existing, allowed_tenants=allowed_tenants)
        if not ok:
            return False, error, None

        existing.append(cleaned)
        save_store(path, existing)
        return True, None, cleaned


def update_extension(path, name: str, data: dict, allowed_tenants=None):
    with _STORE_LOCK:
        if not isinstance(data, dict):
            return False, "dados do ramal devem ser um objeto JSON", None
        if "voicemail_pin" in data:
            return False, "PIN de voicemail não editável pela API", None
        existing = load_store(path)
        if not any(e["name"] == name for e in existing):
            return False, f"ramal '{name}' não encontrado", None

        merged = {**next(e for e in existing if e["name"] == name), **data, "name": name}
        ok, error, cleaned = validate_extension_input(
            merged, existing, editing_name=name, allowed_tenants=allowed_tenants
        )
        if not ok:
            return False, error, None

        updated = [cleaned if e["name"] == name else e for e in existing]
        save_store(path, updated)
        return True, None, cleaned


def delete_extension(path, name: str):
    with _STORE_LOCK:
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
    with _STORE_LOCK:
        existing = load_store(path)
        remaining = [e for e in existing if e.get("tenant", DEFAULT_TENANT) != tenant_id]
        removed_count = len(existing) - len(remaining)
        if removed_count:
            save_store(path, remaining)
        return removed_count

