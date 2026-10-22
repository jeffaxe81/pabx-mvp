import pytest
from presence import save_presence, load_presence


def test_presence_persistence_creates_parent_and_remains_readable(tmp_path):
    path = tmp_path / "nested" / "presence.json"
    data = {"1001": {"status": "ausente", "note": "Almoço"}}
    save_presence(path, data)
    assert load_presence(path) == data
    assert not list(path.parent.glob(".presence.json.*"))


def test_serialization_failure_keeps_last_valid_snapshot(tmp_path):
    path = tmp_path / "presence.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(TypeError):
        save_presence(path, {"bad": object()})
    assert path.read_text(encoding="utf-8") == "{}"
    assert not list(tmp_path.glob(".presence.json.*"))
