import pytest

from store import (
    load_store, save_store, validate_extension_input,
    add_extension, update_extension, delete_extension, delete_extensions_by_tenant,
)

VALID_INPUT = {"name": "recepcao-3", "number": 1112, "display_name": "Recepção 3", "password": "senha-forte"}


def test_load_store_returns_empty_list_when_file_missing(tmp_path):
    assert load_store(tmp_path / "nao-existe.json") == []


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "store.json"
    save_store(path, [VALID_INPUT])
    assert load_store(path) == [VALID_INPUT]


# ---------- validate_extension_input ----------

def test_validate_accepts_correct_input():
    ok, error, cleaned = validate_extension_input(VALID_INPUT, existing=[])
    assert ok is True
    assert cleaned["name"] == "recepcao-3"
    assert cleaned["number"] == 1112
    assert cleaned["tenant"] == "t1"


def test_validate_rejects_invalid_name_characters():
    ok, error, _ = validate_extension_input({**VALID_INPUT, "name": "Recepção 3!"}, existing=[])
    assert ok is False
    assert "nome do ramal" in error


def test_validate_rejects_duplicate_name():
    ok, error, _ = validate_extension_input(VALID_INPUT, existing=[{"name": "recepcao-3", "number": 1113}])
    assert ok is False
    assert "já existe um ramal chamado" in error


def test_validate_rejects_number_out_of_range():
    ok, error, _ = validate_extension_input({**VALID_INPUT, "number": 999}, existing=[])
    assert ok is False
    assert "número deve estar entre" in error


def test_validate_rejects_duplicate_number():
    ok, error, _ = validate_extension_input(VALID_INPUT, existing=[{"name": "outro-ramal", "number": 1112}])
    assert ok is False
    assert "já existe um ramal com o número" in error


def test_validate_generates_password_when_not_provided():
    data = {k: v for k, v in VALID_INPUT.items() if k != "password"}
    ok, error, cleaned = validate_extension_input(data, existing=[])
    assert ok is True
    assert cleaned["password"]  # gerou alguma coisa
    assert len(cleaned["password"]) >= 12


def test_validate_editing_same_name_does_not_conflict_with_itself():
    """Editar um ramal e reenviar o mesmo nome/número não deve disparar 'duplicado'."""
    existing = [{"name": "recepcao-3", "number": 1112}]
    ok, error, cleaned = validate_extension_input(VALID_INPUT, existing, editing_name="recepcao-3")
    assert ok is True


# ---------- add / update / delete ----------

def test_add_extension_persists_to_disk(tmp_path):
    path = tmp_path / "store.json"
    ok, error, cleaned = add_extension(path, VALID_INPUT)
    assert ok is True
    assert load_store(path) == [cleaned]


def test_add_extension_rejects_invalid_data(tmp_path):
    path = tmp_path / "store.json"
    ok, error, cleaned = add_extension(path, {**VALID_INPUT, "number": 1})
    assert ok is False
    assert load_store(path) == []


def test_update_extension_changes_fields(tmp_path):
    path = tmp_path / "store.json"
    add_extension(path, VALID_INPUT)

    ok, error, cleaned = update_extension(path, "recepcao-3", {"display_name": "Recepção Nova"})
    assert ok is True
    assert cleaned["display_name"] == "Recepção Nova"
    assert load_store(path)[0]["display_name"] == "Recepção Nova"


def test_update_extension_rejects_unknown_name(tmp_path):
    path = tmp_path / "store.json"
    ok, error, cleaned = update_extension(path, "nao-existe", {"display_name": "x"})
    assert ok is False
    assert "não encontrado" in error


def test_delete_extension_removes_from_store(tmp_path):
    path = tmp_path / "store.json"
    add_extension(path, VALID_INPUT)

    ok, error = delete_extension(path, "recepcao-3")
    assert ok is True
    assert load_store(path) == []


def test_delete_extension_rejects_unknown_name(tmp_path):
    path = tmp_path / "store.json"
    ok, error = delete_extension(path, "nao-existe")
    assert ok is False


# ---------- Multi-tenant (backlog #38) ----------

def test_validate_accepts_explicit_tenant():
    ok, error, cleaned = validate_extension_input({**VALID_INPUT, "tenant": "t2"}, existing=[])
    assert ok is True
    assert cleaned["tenant"] == "t2"


def test_validate_rejects_unknown_tenant():
    ok, error, _ = validate_extension_input({**VALID_INPUT, "tenant": "t99"}, existing=[])
    assert ok is False
    assert "tenant" in error


def test_same_number_allowed_across_different_tenants():
    """
    Números podem repetir ENTRE tenants (contextos isolados no
    dialplan) - só precisam ser únicos dentro do mesmo tenant.
    """
    existing = [{"name": "vendas-1", "number": 1112, "tenant": "t1"}]
    ok, error, cleaned = validate_extension_input({**VALID_INPUT, "tenant": "t2"}, existing)
    assert ok is True
    assert cleaned["tenant"] == "t2"


def test_same_number_rejected_within_same_tenant():
    existing = [{"name": "vendas-1", "number": 1112, "tenant": "t1"}]
    ok, error, _ = validate_extension_input({**VALID_INPUT, "tenant": "t1"}, existing)
    assert ok is False
    assert "tenant t1" in error


# ---------- delete_extensions_by_tenant (backlog #54) ----------

def test_delete_extensions_by_tenant_removes_only_matching_tenant(tmp_path):
    path = tmp_path / "store.json"
    save_store(path, [
        {"name": "vendas-t3-1", "number": 1112, "tenant": "t3"},
        {"name": "recepcao-3", "number": 1113, "tenant": "t1"},
    ])

    removed_count = delete_extensions_by_tenant(path, "t3")

    assert removed_count == 1
    remaining = load_store(path)
    assert [e["name"] for e in remaining] == ["recepcao-3"]


def test_delete_extensions_by_tenant_removes_multiple_at_once(tmp_path):
    path = tmp_path / "store.json"
    save_store(path, [
        {"name": "vendas-t3-1", "number": 1112, "tenant": "t3"},
        {"name": "suporte-t3-1", "number": 1113, "tenant": "t3"},
    ])

    removed_count = delete_extensions_by_tenant(path, "t3")

    assert removed_count == 2
    assert load_store(path) == []


def test_delete_extensions_by_tenant_returns_zero_when_none_match(tmp_path):
    path = tmp_path / "store.json"
    save_store(path, [{"name": "recepcao-3", "number": 1112, "tenant": "t1"}])

    removed_count = delete_extensions_by_tenant(path, "t3")

    assert removed_count == 0
    assert len(load_store(path)) == 1  # nada foi tocado


def test_delete_extensions_by_tenant_handles_missing_store_file(tmp_path):
    path = tmp_path / "nao-existe.json"
    assert delete_extensions_by_tenant(path, "t3") == 0
