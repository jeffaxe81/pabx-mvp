import pytest
import tenant_registry_recovery as recovery

def test_registry_snapshot_rejects_excessive_size(tmp_path, monkeypatch):
    path = tmp_path / "tenants.json"
    path.write_bytes(b"1234567890")
    monkeypatch.setattr(recovery, "MAX_REGISTRY_SNAPSHOT_BYTES", 9)
    with pytest.raises(ValueError):
        recovery.snapshot_registry(path)
    monkeypatch.setattr(recovery, "MAX_REGISTRY_SNAPSHOT_BYTES", 10)
    snapshot = recovery.snapshot_registry(path)
    assert snapshot[0] == b"1234567890"
