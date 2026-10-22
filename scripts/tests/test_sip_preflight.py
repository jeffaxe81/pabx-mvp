"""Regressões do diagnóstico SIP - nenhuma chamada externa ou Docker real."""
import json
import subprocess
from unittest.mock import patch

import pytest
import sip_preflight


def good_snapshots():
    return {
        "version": {"code": 0, "output": "Asterisk 22.0.0 built by tests"},
        "transports": {"code": 0, "output": (
            "Transport: transport-tls tls 0.0.0.0:5061\n"
            "Transport: transport-wss wss 0.0.0.0"
        )},
        "endpoints": {"code": 0, "output": (
            "Endpoint: t1-1001/1001 Not in use\n"
            "Endpoint: t2-1001/1001 Unavailable"
        )},
        "dialplan": {"code": 0, "output": (
            "_X. => Set(TENANT=DB(tenant-did/1234))\n"
            "GotoIf(...?did-desconhecido,1)\n"
            "did-desconhecido => Hangup(21)"
        )},
        "channels": {"code": 0, "output": "0 active channels\n0 calls processed"},
    }


def test_success_does_not_claim_real_sip_or_rtp_testing():
    result = sip_preflight.analyze_snapshots(good_snapshots())
    assert result["ok"] is True
    assert result["active_channels"] == 0
    assert result["call_tested"] is False
    assert result["rtp_tested"] is False
    assert result["tenant_isolation_tested_on_live_calls"] is False


def test_did_missing_rejection_fails_gate():
    snapshot = good_snapshots()
    snapshot["dialplan"]["output"] = "Goto(ura-principal,s,1)"
    result = sip_preflight.analyze_snapshots(snapshot)
    assert result["ok"] is False
    assert result["checks"]["did_fail_closed"]["ok"] is False


def test_tls_or_wss_missing_fails_gate():
    snapshot = good_snapshots()
    snapshot["transports"]["output"] = "Transport: transport-udp udp 0.0.0.0:5060"
    result = sip_preflight.analyze_snapshots(snapshot)
    assert not result["checks"]["transport-tls"]["ok"]
    assert not result["checks"]["transport-wss"]["ok"]


def test_missing_endpoint_is_reported_without_exposing_cli():
    snapshot = good_snapshots()
    snapshot["endpoints"]["output"] = "Endpoint: t1-1001/1001"
    result = sip_preflight.analyze_snapshots(snapshot)
    assert not result["checks"]["endpoint:t2-1001"]["ok"]
    assert "Endpoint: t1-1001" not in json.dumps(result)


def test_failed_cli_command_is_not_treated_as_valid_evidence():
    snapshot = good_snapshots()
    snapshot["dialplan"] = {"code": 1, "output": (
        "did-desconhecido tenant-did/ Hangup(21)"
    )}
    assert not sip_preflight.analyze_snapshots(snapshot)["ok"]


def test_rejects_unsafe_expected_endpoint_name():
    with pytest.raises(ValueError):
        sip_preflight.analyze_snapshots(good_snapshots(), ["t1-1001\nAction: Command"])


def test_runner_uses_fixed_read_only_commands_and_no_shell():
    recorded = []
    def fake_run(argv, **kwargs):
        recorded.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "Asterisk output", "")

    with patch("sip_preflight.subprocess.run", side_effect=fake_run):
        snapshots = sip_preflight.collect_snapshots()
    assert len(snapshots) == len(sip_preflight.COMMANDS)
    for argv, kwargs in recorded:
        assert argv[:4] == ["docker", "exec", "pabx-mvp", "asterisk"]
        assert argv[4] == "-rx"
        assert argv[5] in sip_preflight.COMMANDS.values()
        assert kwargs["check"] is False
        assert kwargs["timeout"] == 8
        assert "shell" not in kwargs
    assert all(entry["code"] == 0 for entry in snapshots.values())


def test_local_runtime_does_not_call_docker():
    with patch("sip_preflight.subprocess.run", return_value=subprocess.CompletedProcess(
        ["asterisk"], 0, "Asterisk output", ""
    )) as mocked:
        sip_preflight.collect_snapshots(runtime="local")
    assert mocked.call_args.args[0][:2] == ["asterisk", "-rx"]


def test_rejects_unsafe_container_without_calling_process():
    with patch("sip_preflight.subprocess.run") as mocked:
        with pytest.raises(ValueError):
            sip_preflight.collect_snapshots(container="pabx; rm -rf /")
        mocked.assert_not_called()


def test_timeout_is_reported_as_unavailable():
    with patch("sip_preflight.subprocess.run", side_effect=subprocess.TimeoutExpired(
        "asterisk", 1
    )):
        snapshots = sip_preflight.collect_snapshots()
    assert all(row == {"code": None, "output": ""} for row in snapshots.values())
    assert not sip_preflight.analyze_snapshots(snapshots)["ok"]


def test_main_prints_json_and_exits_success_when_checks_pass(capsys):
    with patch("sip_preflight.collect_snapshots", return_value=good_snapshots()):
        code = sip_preflight.main(["--runtime", "local"])
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert report["runtime"] == "local"
    assert report["ok"] is True
    assert "timestamp_utc" in report


def test_main_rejects_unreasonable_timeout():
    with pytest.raises(SystemExit) as exc:
        sip_preflight.main(["--timeout", "60"])
    assert exc.value.code == 2
