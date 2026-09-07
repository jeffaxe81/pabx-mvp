from presence import (
    validate_presence_input, load_presence, save_presence,
    set_presence, clear_presence, merge_presence_into_states,
)


# ---------- validate_presence_input ----------

def test_validate_accepts_known_states():
    for status in ("disponivel", "ausente", "reuniao", "ferias"):
        ok, error, cleaned = validate_presence_input({"status": status})
        assert ok is True
        assert cleaned["status"] == status


def test_validate_rejects_unknown_status():
    ok, error, _ = validate_presence_input({"status": "dormindo"})
    assert ok is False
    assert "inválido" in error


def test_validate_rejects_empty_status():
    ok, error, _ = validate_presence_input({})
    assert ok is False


def test_validate_accepts_optional_note():
    ok, error, cleaned = validate_presence_input({"status": "reuniao", "note": "Reunião com fornecedor até 15h"})
    assert ok is True
    assert cleaned["note"] == "Reunião com fornecedor até 15h"


def test_validate_note_defaults_to_empty_string():
    ok, error, cleaned = validate_presence_input({"status": "ausente"})
    assert cleaned["note"] == ""


# ---------- load/save/set/clear ----------

def test_load_presence_missing_file_returns_empty_dict(tmp_path):
    assert load_presence(tmp_path / "nao-existe.json") == {}


def test_set_presence_persists(tmp_path):
    path = tmp_path / "presence.json"
    entry = set_presence(path, "t1-recepcao", "ferias", "De volta dia 10")

    assert entry["status"] == "ferias"
    assert entry["note"] == "De volta dia 10"
    assert entry["updated_at"] is not None

    reloaded = load_presence(path)
    assert reloaded["t1-recepcao"]["status"] == "ferias"


def test_set_presence_overwrites_previous_value(tmp_path):
    path = tmp_path / "presence.json"
    set_presence(path, "t1-recepcao", "ausente")
    set_presence(path, "t1-recepcao", "reuniao")

    assert load_presence(path)["t1-recepcao"]["status"] == "reuniao"


def test_set_presence_does_not_affect_other_extensions(tmp_path):
    path = tmp_path / "presence.json"
    set_presence(path, "t1-recepcao", "ausente")
    set_presence(path, "t1-recepcao-2", "reuniao")

    data = load_presence(path)
    assert data["t1-recepcao"]["status"] == "ausente"
    assert data["t1-recepcao-2"]["status"] == "reuniao"


def test_clear_presence_removes_override(tmp_path):
    path = tmp_path / "presence.json"
    set_presence(path, "t1-recepcao", "ferias")

    ok = clear_presence(path, "t1-recepcao")
    assert ok is True
    assert "t1-recepcao" not in load_presence(path)


def test_clear_presence_returns_false_when_nothing_to_clear(tmp_path):
    path = tmp_path / "presence.json"
    assert clear_presence(path, "t1-recepcao") is False


# ---------- merge_presence_into_states ----------

def test_merge_adds_manual_status_when_override_exists():
    states = [{"exten": "1010", "status_label": "livre"}]
    presence_map = {"1010": {"status": "ferias", "note": "De volta dia 10"}}

    merged = merge_presence_into_states(states, presence_map)
    assert merged[0]["manual_status"] == "ferias"
    assert merged[0]["manual_note"] == "De volta dia 10"
    assert merged[0]["status_label"] == "livre"  # estado automático preservado


def test_merge_sets_none_when_no_override():
    states = [{"exten": "1010", "status_label": "livre"}]
    merged = merge_presence_into_states(states, {})
    assert merged[0]["manual_status"] is None
    assert merged[0]["manual_note"] is None


def test_merge_handles_multiple_extensions_independently():
    states = [
        {"exten": "1010", "status_label": "livre"},
        {"exten": "1011", "status_label": "ocupado"},
    ]
    presence_map = {"1010": {"status": "ausente", "note": ""}}

    merged = merge_presence_into_states(states, presence_map)
    assert merged[0]["manual_status"] == "ausente"
    assert merged[1]["manual_status"] is None
