import json
import pytest
from tenants import save_tenants, load_tenants


def test_tenants_write_json_atomically(tmp_path):
    path = tmp_path / "nested" / "tenants.json"
    data = [{"tenant_id": "t3", "did": "11999998888", "display_name": "Loja"}]
    save_tenants(path, data)
    assert load_tenants(path) == data
    assert json.loads(path.read_text(encoding="utf-8")) == data
    assert not list(path.parent.glob(".tenants.json.*"))


def test_serialization_failure_preserves_previous_file(tmp_path):
    path = tmp_path / "tenants.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(TypeError):
        save_tenants(path, [object()])
    assert path.read_text(encoding="utf-8") == "[]"
    assert not list(tmp_path.glob(".tenants.json.*"))
