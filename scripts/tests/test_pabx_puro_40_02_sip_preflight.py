"""Bateria PABX puro #11-20: diagnóstico somente leitura, sem chamadas reais."""
import json
import pytest
from sip_preflight import analyze_snapshots
from voicemail_pin_audit import audit_voicemail_text, audit_voicemail_files


def snapshots():
    return {
        "version": {"code": 0, "output": "Asterisk 22.1.0"},
        "transports": {"code": 0, "output": "Transport: transport-tls tls\nTransport: transport-wss wss"},
        "endpoints": {"code": 0, "output": "Endpoint: t1-1001/1001\nEndpoint: t2-1001/1001"},
        "dialplan": {"code": 0, "output": "tenant-did/\ndid-desconhecido\nHangup(21)"},
        "channels": {"code": 0, "output": "0 active channels"},
    }


def test_11_preflight_detects_config_without_claiming_live_call():
    result = analyze_snapshots(snapshots())
    assert result["ok"]
    assert not result["call_tested"]
    assert not result["rtp_tested"]


def test_12_preflight_reports_unknown_did_route_removed():
    src = snapshots()
    src["dialplan"]["output"] = "tenant-did/\nHangup(21)"
    assert not analyze_snapshots(src)["checks"]["did_fail_closed"]["ok"]


def test_13_preflight_rejects_missing_tls_transport():
    src = snapshots()
    src["transports"]["output"] = "transport-wss"
    assert not analyze_snapshots(src)["checks"]["transport-tls"]["ok"]


def test_14_preflight_rejects_missing_wss_transport():
    src = snapshots()
    src["transports"]["output"] = "transport-tls"
    assert not analyze_snapshots(src)["checks"]["transport-wss"]["ok"]


def test_15_preflight_never_confuses_t1_with_t10():
    result = analyze_snapshots(snapshots(), expected_endpoints=["t10-1001"])
    assert not result["checks"]["endpoint:t10-1001"]["ok"]


def test_16_preflight_ignores_endpoint_listing_when_cli_failed():
    src = snapshots()
    src["endpoints"]["code"] = 1
    assert not analyze_snapshots(src)["checks"]["endpoint:t1-1001"]["ok"]


def test_17_preflight_extracts_asterisk_channel_count():
    src = snapshots()
    src["channels"]["output"] = "27 active channels"
    assert analyze_snapshots(src)["active_channels"] == 27


def test_18_preflight_summary_does_not_leak_sip_cli_secrets():
    src = snapshots()
    src["endpoints"]["output"] += "\nAuthorization: Bearer secret-key"
    assert "secret-key" not in json.dumps(analyze_snapshots(src))


def test_19_voicemail_audit_rejects_reused_pin_across_tenants():
    src = "[t1]\nt1-1001 => 93847261,Um\n[t10]\nt10-1001 => 93847261,Dez\n"
    report = audit_voicemail_text(src)
    assert not report["ok"]
    assert report["reused_pins"] == 1
    assert "93847261" not in json.dumps(report)


def test_20_voicemail_audit_rejects_symlink_to_private_mailbox_config(tmp_path):
    real = tmp_path / "voicemail.conf"
    real.write_text("[t1]\nt1-1001 => 93847261,Um\n")
    link = tmp_path / "symlink.conf"
    link.symlink_to(real)
    assert audit_voicemail_files([link])["ok"] is False
    assert audit_voicemail_files([real])["ok"] is True
