"""Real CLI audit validation; fake CLI fixtures, not a runtime call."""
import pytest
import asterisk_lab_audit as audit
from test_asterisk_lab_audit import snapshots

def test_asterisk_audit_valid_cli_output_still_accepted():
    assert audit.check_snapshots(snapshots({}), {})["ready_for_call_homologation"]

@pytest.mark.parametrize("text", [
    "Transport: transport-wss wss\nError: transport-tls not found",
    "Transport: transport-tls-test tls\nTransport: transport-wss wss",
    "missing transport-tls\nTransport: transport-wss wss",
])
def test_asterisk_audit_requires_real_transport_entry_not_warning(text):
    src=snapshots({})
    src["transports"]["output"]=text
    assert not audit.check_snapshots(src,{})["checks"]["transport:transport-tls"]

@pytest.mark.parametrize("bad", [None, [], 42, {"code":0,"output":None},
                                    {"code":True,"output":"Asterisk 22"}])
def test_cli_audit_rejects_corrupt_records_without_crashing(bad):
    src=snapshots({})
    src["version"]=bad
    assert not audit.check_snapshots(src,{})["checks"]["runtime_version"]

def test_cli_audit_limits_untrusted_output():
    src=snapshots({})
    src["transports"]["output"]="Transport: transport-tls tls\n"+("x"*200000)
    assert not audit.check_snapshots(src,{})["checks"]["transport:transport-tls"]

def test_cli_audit_registry_maximum_size_is_fail_closed(tmp_path,monkeypatch):
    path=tmp_path/"tenants.json"
    path.write_text("[]")
    monkeypatch.setattr(audit,"MAX_REGISTRY_BYTES",1)
    with pytest.raises(ValueError):
        audit.read_expected_tenants(path)

def test_cli_audit_registry_cannot_traverse_symlinked_parent(tmp_path):
    real=tmp_path/"real"
    real.mkdir()
    (real/"tenants.json").write_text("[]")
    link=tmp_path/"alias"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError):
        audit.read_expected_tenants(link/"tenants.json")

def test_cli_audit_rejects_boolean_timeout():
    with pytest.raises(ValueError):
        audit.run_cli({"version":"core show version"},timeout=True)
