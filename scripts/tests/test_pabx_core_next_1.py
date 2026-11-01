"""Telephony-only negative checks of read-only SIP CLI observations."""
import pytest
import sip_preflight as audit

def healthy():
    return {
        "version":{"code":0,"output":"Asterisk 22.11"},
        "transports":{"code":0,"output":"Transport: transport-tls tls\nTransport: transport-wss wss"},
        "endpoints":{"code":0,"output":"Endpoint: t1-1001/1001\nEndpoint: t2-1001/1001"},
        "dialplan":{"code":0,"output":"tenant-did/\ndid-desconhecido\nHangup(21)"},
        "channels":{"code":0,"output":"0 active channels"}
    }

def test_preflight_sip_nominal_configuration_only():
    result=audit.analyze_snapshots(healthy())
    assert result["ok"] and not result["call_tested"]

@pytest.mark.parametrize("text", [
    "Error: transport-tls missing\nTransport: transport-wss wss",
    "Transport: transport-tls-other tls\nTransport: transport-wss wss",
    "Untrusted warning: transport-tls\nTransport: transport-wss wss",
])
def test_preflight_never_accepts_transport_mentioned_only_in_diagnostic(text):
    rows=healthy()
    rows["transports"]["output"]=text
    assert not audit.analyze_snapshots(rows)["checks"]["transport-tls"]["ok"]

@pytest.mark.parametrize("bad", [None, [], 12, {"code":0,"output":None}, {"code":True,"output":"Asterisk 22"}])
def test_preflight_corrupt_cli_record_is_not_evidence(bad):
    rows=healthy()
    rows["version"]=bad
    assert not audit.analyze_snapshots(rows)["checks"]["asterisk_cli"]["ok"]

def test_preflight_rejects_excessive_cli_output_without_echo():
    rows=healthy()
    rows["version"]["output"]="Asterisk 22\n"+("secret" * 30000)
    summary=audit.analyze_snapshots(rows)
    assert not summary["checks"]["asterisk_cli"]["ok"]
    assert "secret" not in str(summary)

@pytest.mark.parametrize("identities", [None, [], ["t1-1001","t1-1001"], ["t1-1001\nAttack"], list(range(31))])
def test_preflight_fails_closed_on_invalid_endpoint_expectation(identities):
    with pytest.raises(ValueError):
        audit.analyze_snapshots(healthy(), identities)
