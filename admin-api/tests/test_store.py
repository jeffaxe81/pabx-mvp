import pytest

from store import (
    load_store, save_store, validate_extension_input,
    add_extension, update_extension, delete_extension, delete_extensions_by_tenant,
)

VALID_INPUT = {"name": "recepcao-3", "number": 1112, "display_name": "Recepção 3", "password": "senha-forte-2026"}


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


# ---------- Regressão de tipos e injeção em configuração ----------

@pytest.mark.parametrize("payload", [None, [], "bad", 42, True])
def test_validation_rejects_non_object_json_payload(payload):
    ok, error, cleaned = validate_extension_input(payload, [])
    assert not ok and error and cleaned is None


@pytest.mark.parametrize("field,value", [
    ("name", ["ramal"]),
    ("name", 1234),
    ("tenant", ["t1"]),
    ("number", True),
    ("number", 1100.1),
    ("number", "1100\nSet(MALICIOUS=yes)"),
    ("display_name", ["Vendas"]),
    ("email", {"to": "mail@domain.com"}),
    ("password", {"value": "secret"}),
])
def test_validation_rejects_wrong_field_types(field, value):
    ok, error, cleaned = validate_extension_input(
        {**VALID_INPUT, field: value}, []
    )
    assert not ok and error and cleaned is None


@pytest.mark.parametrize("field,value", [
    ("name", "vendas-1\n"),
    ("display_name", "Operador\r\n[malicious]"),
    ("display_name", "Nome,secret=123"),
    ("display_name", "Nome <injetado>"),
    ("email", "user@example.com\n[global]"),
    ("email", "user@example.com,Inject"),
    ("password", "SegredoMuitoForte\n[operator]"),
    ("password", "SegredoMuito;Comment"),
])
def test_validation_blocks_asterisk_config_injection(field, value):
    ok, error, cleaned = validate_extension_input(
        {**VALID_INPUT, field: value}, []
    )
    assert not ok and cleaned is None, (field, value, error)


def test_validation_allows_ordinary_diacritics_and_email():
    payload = {**VALID_INPUT, "display_name": "Recepção São José",
               "email": "atendimento+sp@empresa.com.br"}
    ok, error, cleaned = validate_extension_input(payload, [])
    assert ok and error is None
    assert cleaned["display_name"] == "Recepção São José"


def test_missing_password_generates_secure_long_random_secret():
    payload = {**VALID_INPUT, "password": ""}
    a = validate_extension_input(payload, [])[2]["password"]
    b = validate_extension_input(payload, [])[2]["password"]
    assert a != b
    assert len(a) >= 32 and len(b) >= 32


def test_password_short_on_create_rejected_but_legacy_kept_on_edit():
    payload = {**VALID_INPUT, "password": "oldsecret"}
    ok, _, _ = validate_extension_input(payload, [])
    assert not ok
    legacy = [{**payload}]
    ok, _, cleaned = validate_extension_input(payload, legacy, editing_name=payload["name"])
    assert ok and cleaned["password"] == "oldsecret"
    rotated = {**payload, "password": "newsecret"}
    ok, _, _ = validate_extension_input(rotated, legacy, editing_name=payload["name"])
    assert not ok


@pytest.mark.parametrize("registry", [
    [None], [{}], [{"name": "vendas-1", "number": "oops"}],
    [{"name": "vendas-1", "number": True}],
])
def test_registry_corruption_fails_closed(registry):
    ok, error, cleaned = validate_extension_input(VALID_INPUT, registry)
    assert not ok and cleaned is None and "cadastro" in error

def test_generated_voicemail_pins_are_numeric_and_distinct(tmp_path):
    path = tmp_path / "ramais.json"
    first = {**VALID_INPUT, "name": "recepcao-3", "number": 1112}
    second = {**VALID_INPUT, "name": "recepcao-4", "number": 1113}
    a = add_extension(path, first)[2]
    b = add_extension(path, second)[2]
    assert len(a["voicemail_pin"]) == 8
    assert a["voicemail_pin"].isdigit()
    assert a["voicemail_pin"][0] != "0"
    assert a["voicemail_pin"] != b["voicemail_pin"]
    assert load_store(path)[0]["voicemail_pin"] == a["voicemail_pin"]


def test_update_preserves_existing_voicemail_pin(tmp_path):
    path = tmp_path / "ramais.json"
    created = add_extension(path, VALID_INPUT)[2]
    changed = update_extension(path, created["name"], {"display_name": "Recepção Nova"})[2]
    assert changed["voicemail_pin"] == created["voicemail_pin"]


def test_post_and_put_cannot_choose_voicemail_pin(tmp_path):
    path = tmp_path / "ramais.json"
    bad = {**VALID_INPUT, "voicemail_pin": "00000000"}
    ok, error, _ = add_extension(path, bad)
    assert not ok and "PIN" in error
    add_extension(path, VALID_INPUT)
    ok, error, _ = update_extension(path, VALID_INPUT["name"], {"voicemail_pin": "1234"})
    assert not ok and "PIN" in error


def test_legacy_voicemail_pin_requires_explicit_migration(tmp_path):
    path = tmp_path / "ramais.json"
    legacy = {**VALID_INPUT, "tenant": "t1"}
    save_store(path, [legacy])
    ok, error, edited = update_extension(path, legacy["name"], {"display_name": "Atualizado"})
    assert not ok and edited is None
    assert "migração" in error
    assert load_store(path) == [legacy]


def test_registered_tenant_t3_can_create_and_update_extension(tmp_path):
    path = tmp_path / "ramais.json"
    data = {**VALID_INPUT, "name": "tres-ramal", "tenant": "t3"}
    ok, error, created = add_extension(path, data, allowed_tenants={"t1", "t2", "t3"})
    assert ok, error
    assert created["tenant"] == "t3"
    ok, error, updated = update_extension(
        path, "tres-ramal", {"display_name": "Atendente t3"},
        allowed_tenants={"t1", "t2", "t3"}
    )
    assert ok, error
    assert updated["tenant"] == "t3"


def test_unknown_tenant_cannot_create_even_if_payload_requests_it(tmp_path):
    path = tmp_path / "ramais.json"
    request = {**VALID_INPUT, "tenant": "t3"}
    ok, error, cleaned = add_extension(path, request, allowed_tenants={"t1", "t2"})
    assert not ok and cleaned is None and "tenant inválido" in error
    assert load_store(path) == []


def test_bad_tenant_registry_fails_closed():
    ok, error, cleaned = validate_extension_input(
        {**VALID_INPUT, "tenant": "t3"}, [], allowed_tenants={"t1", "../t3"}
    )
    assert not ok and cleaned is None and "registro" in error


def test_t3_duplicate_number_fails_only_inside_same_tenant():
    original = {**VALID_INPUT, "tenant": "t3"}
    existing = [{**original}]
    ok, error, _ = validate_extension_input(
        {**VALID_INPUT, "name": "novo-ramal", "tenant": "t3"},
        existing, allowed_tenants={"t1", "t2", "t3"}
    )
    assert not ok and "t3" in error
    ok, error, cleaned = validate_extension_input(
        {**VALID_INPUT, "name": "novo-ramal", "tenant": "t2"},
        existing, allowed_tenants={"t1", "t2", "t3"}
    )
    assert ok and cleaned["tenant"] == "t2"

# ---------- armazenamento atômico e concorrência local ----------

def test_atomic_store_keeps_previous_snapshot_if_replace_fails(tmp_path, monkeypatch):
    import store
    target = tmp_path / "extensions.json"
    original = [{**VALID_INPUT}]
    save_store(target, original)
    previous_bytes = target.read_bytes()

    def interrupted_replace(src, dst):
        raise OSError("falha simulada antes da troca")

    monkeypatch.setattr(store.os, "replace", interrupted_replace)
    with pytest.raises(OSError, match="falha simulada"):
        save_store(target, [{**VALID_INPUT, "name": "ramal-novo"}])
    assert target.read_bytes() == previous_bytes
    assert not list(tmp_path.glob(".extensions.json.*"))


def test_atomic_store_keeps_previous_snapshot_if_json_write_fails(tmp_path, monkeypatch):
    import store
    target = tmp_path / "extensions.json"
    save_store(target, [VALID_INPUT])
    previous_bytes = target.read_bytes()

    def interrupted_dump(value, handle, **kwargs):
        handle.write('{"ramais":')
        raise OSError("interrupção simulada na escrita")

    monkeypatch.setattr(store.json, "dump", interrupted_dump)
    with pytest.raises(OSError, match="interrupção simulada"):
        save_store(target, [{"name": "outro"}])
    assert target.read_bytes() == previous_bytes
    assert not list(tmp_path.glob(".extensions.json.*"))


def test_atomic_store_replaces_insecure_existing_file_permissions(tmp_path):
    import stat
    target = tmp_path / "extensions.json"
    target.write_text("[]", encoding="utf-8")
    target.chmod(0o644)
    save_store(target, [VALID_INPUT])
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert load_store(target) == [VALID_INPUT]


def test_atomic_store_rejects_symlinks_without_touching_target(tmp_path):
    target = tmp_path / "important.json"
    target.write_text("sensitive", encoding="utf-8")
    link = tmp_path / "extensions.json"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="simbólico"):
        load_store(link)
    with pytest.raises(ValueError, match="simbólico"):
        save_store(link, [])
    assert target.read_text(encoding="utf-8") == "sensitive"


def test_atomic_store_does_not_treat_invalid_existing_json_as_empty(tmp_path):
    target = tmp_path / "extensions.json"
    target.write_text('{"not": "list"}', encoding="utf-8")
    with pytest.raises(ValueError, match="lista JSON"):
        load_store(target)
    target.write_text("[bad", encoding="utf-8")
    with pytest.raises(ValueError):
        add_extension(target, VALID_INPUT)
    assert target.read_text(encoding="utf-8") == "[bad"


def test_concurrent_admin_creations_keep_all_extensions(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    target = tmp_path / "extensions.json"
    records = [
        {**VALID_INPUT, "name": f"posto-{i:02d}", "number": 1100 + i}
        for i in range(30)
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda payload: add_extension(target, payload), records))

    assert all(ok and not error for ok, error, _ in results)
    saved = load_store(target)
    assert len(saved) == 30
    assert len({record["name"] for record in saved}) == 30
    assert len({record["number"] for record in saved}) == 30
    assert not list(tmp_path.glob(".extensions.json.*"))


def test_simultaneous_same_number_only_one_creation_succeeds(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    target = tmp_path / "extensions.json"
    records = [
        {**VALID_INPUT, "name": f"agent-{i}", "number": 1110}
        for i in range(12)
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda item: add_extension(target, item), records))
    assert sum(ok for ok, _, _ in results) == 1
    assert len(load_store(target)) == 1
