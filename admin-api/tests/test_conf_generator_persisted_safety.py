"""Falha segura na ultima barreira entre JSON persistido e .conf Asterisk."""
import copy

import pytest

from conf_generator import render_all, validate_persisted_extensions


BASE = {
    "name": "suporte-01",
    "number": 1112,
    "display_name": "Recepção São José",
    "password": "senha-forte-2026",
    "tenant": "t1",
    "email": "ramal+teste@empresa.com.br",
    "voicemail_pin": "87654321",
}


def test_valid_legacy_and_modern_records_continue_separated():
    legacy = {**BASE, "name": "legado-01", "number": "1113"}
    legacy.pop("tenant")
    legacy.pop("voicemail_pin")
    newer = {**BASE, "name": "t3-1001", "tenant": "t3", "number": 1112}
    allowed = {"t1", "t2", "t3"}
    files = render_all([legacy, newer], tenant_ids=allowed)
    assert "legado-01" in files["extensions_dynamic_dial-t1.conf"]
    assert "legado-01" not in files["extensions_dynamic_dial-t3.conf"]
    assert "t3-1001" in files["extensions_dynamic_dial-t3.conf"]
    assert "t3-1001" not in files["extensions_dynamic_dial-t1.conf"]
    assert "mailboxes=t3-1001@t3" in files["pjsip_dynamic.conf"]
    assert "legado-01 => 1234" in files["voicemail_dynamic_t1.conf"]


@pytest.mark.parametrize("change", [
    {"name": "t2-1002"},
    {"name": "t10-1001"},
    {"name": "t1-1001"},
    {"name": "t1-recepcao"},
    {"name": "t1-recepcao-2"},
    {"name": "foo\n[global]\n"},
    {"name": "[malicious]"},
    {"number": "1112\nexten => 1"},
    {"number": 1200},
    {"number": True},
    {"display_name": "Operador\n[malicious]"},
    {"display_name": "Abc,context=t2"},
    {"password": "forte\n[malicious]"},
    {"password": {"secret": "confidential"}},
    {"email": "a@example.org\n[general]"},
    {"voicemail_pin": "12\n[global]"},
    {"voicemail_pin": "00000000"},
    {"voicemail_pin": 1234},
    {"tenant": "t4"},
    {"tenant": "t10"},
    {"tenant": 2},
])
def test_corrupted_persisted_fields_abort_generation(change):
    poisoned = {**BASE, **change}
    with pytest.raises(ValueError) as exc:
        render_all([poisoned], tenant_ids={"t1", "t2", "t3"})
    # Nenhum detalhe privado do cadastro pode aparecer no erro.
    assert "senha-forte-2026" not in str(exc.value)
    assert "ramal+teste@empresa.com.br" not in str(exc.value)


@pytest.mark.parametrize("data", [
    None, {}, "invalid", [{"tenant": "t1"}],
    [None], [23], ["malicious"],
])
def test_non_list_or_non_records_fail_before_publication(data):
    with pytest.raises(ValueError):
        render_all(data, tenant_ids={"t1", "t2"})


def test_duplicate_name_across_tenants_fails_closed():
    duplicate = {**BASE, "tenant": "t2", "number": 1114}
    with pytest.raises(ValueError, match="duplicado"):
        render_all([BASE, duplicate], tenant_ids={"t1", "t2"})


def test_duplicate_number_inside_tenant_fails_closed():
    duplicate = {**BASE, "name": "ramal-02"}
    with pytest.raises(ValueError, match="repetido"):
        render_all([BASE, duplicate], tenant_ids={"t1", "t2"})


def test_same_number_in_distinct_tenants_is_supported():
    duplicate_number = {**BASE, "name": "ramal-t2", "tenant": "t2"}
    result = render_all([BASE, duplicate_number], tenant_ids={"t1", "t2"})
    assert "suporte-01" in result["extensions_dynamic_dial-t1.conf"]
    assert "ramal-t2" in result["extensions_dynamic_dial-t2.conf"]


def test_input_snapshot_not_mutated_even_when_validation_fails():
    input_records = [copy.deepcopy(BASE), {**BASE, "name": "t2-1001"}]
    before = copy.deepcopy(input_records)
    with pytest.raises(ValueError):
        render_all(input_records, tenant_ids={"t1", "t2"})
    assert input_records == before


def test_direct_guard_checks_active_tenant_allowlist():
    valid = [{**BASE, "name": "t3-1001", "tenant": "t3"}]
    assert validate_persisted_extensions(valid, {"t1", "t2", "t3"}) is None
    with pytest.raises(ValueError, match="não provisionado"):
        validate_persisted_extensions(valid, {"t1", "t2"})
