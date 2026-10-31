import pytest
from tenant_registry_recovery import restore_registry

def test_registry_restore_rejects_untrusted_snapshot_before_touching_file(tmp_path):
    path = tmp_path/"tenants.json"
    path.write_text("original")
    for bad in ([], ("malformed", 0o600), (b"abc", True), (b"abc", 0o1000), (b"abc",)):
        with pytest.raises(ValueError):
            restore_registry(path, bad)
        assert path.read_text() == "original"
