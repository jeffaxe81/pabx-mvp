"""Testes do laboratório CLI: nenhum Asterisk ou Docker real é iniciado."""
import json
import subprocess
from unittest.mock import patch

import pytest
import asterisk_lab_audit as lab


def expected():
    return {"t3": "5511900003333", "t10": "5511900001010"}


def snapshots(mapping=None):
    mapping = expected() if mapping is None else mapping
    result = {}
    for key in lab.planned_commands(mapping):
        if key == "version":
            output = "Asterisk 22.0.0 test"
        elif key == "transports":
            output = "Transport: transport-tls tls\nTransport: transport-wss wss"
        elif key == "ingress":
            output = "DB(tenant-did/123)\ndid-desconhecido Hangup(21)"
        elif key == "astdb":
            output = "".join(
                f"/tenant-did/{did} : {tid}\n" for tid, did in mapping.items()
            )
        elif key.startswith("endpoint:"):
            tid = key.split(":")[1]
            endpoint = lab.STATIC_ENDPOINTS.get(tid, tid + "-recepcao")
            output = f"Endpoint: {endpoint}/1001 Not in use\nContext: {tid}-internal\n"
        elif key.startswith("context:"):
            tid = key.split(":")[1]
            output = f"[ Context '{tid}-internal' created by 'pbx_config' ]"
        else:
            raise AssertionError(key)
        result[key] = {"code": 0, "output": output, "truncated": False}
    return result


def test_good_runtime_audit_does_not_claim_sip_call_or_rtp():
    report = lab.check_snapshots(snapshots(), expected())
    assert report["ready_for_call_homologation"]
    assert report["passed"] == report["total"]
    assert report["percent"] == 100
    for name in ("registration_verified", "sip_call_tested", "rtp_tested",
                 "srtp_tested", "live_tenant_isolation_tested",
                 "backup_restore_tested"):
        assert report[name] is False


def test_wrong_endpoint_context_is_failure_without_secret_leak():
    snaps = snapshots()
    snaps["endpoint:t3"]["output"] = (
        "Endpoint: t3-recepcao/1001\nContext: t1-internal\n"
        "password=SECRET_PRIVATE"
    )
    report = lab.check_snapshots(snaps, expected())
    assert not report["checks"]["endpoint_context:t3"]
    assert "SECRET_PRIVATE" not in json.dumps(report)


def test_missing_endpoint_and_bad_did_mapping_both_fail():
    snaps = snapshots()
    snaps["endpoint:t10"]["output"] = "Unable to find object"
    snaps["astdb"]["output"] = "/tenant-did/5511900003333 : t10"
    report = lab.check_snapshots(snaps, expected())
    assert not report["checks"]["endpoint_exists:t10"]
    assert not report["checks"]["did_mapping:t3"]
    assert not report["checks"]["did_mapping:t10"]
    assert "5511900003333" not in json.dumps(report)


def test_duplicate_did_lines_do_not_count_as_verified_mapping():
    snaps = snapshots()
    snaps["astdb"]["output"] += "/tenant-did/5511900003333 : t3\n"
    assert not lab.check_snapshots(snaps, expected())["checks"]["did_mapping:t3"]


def test_missing_transport_or_ingress_rejection_fails():
    snaps = snapshots()
    snaps["transports"]["output"] = "Transport: transport-udp udp"
    snaps["ingress"]["output"] = "Goto(ura-principal,s,1)"
    report = lab.check_snapshots(snaps, expected())
    assert not report["checks"]["transport:transport-tls"]
    assert not report["checks"]["transport:transport-wss"]
    assert not report["checks"]["ingress_unknown_did_rejection"]


def test_failed_and_truncated_cli_output_are_not_trusted():
    snaps = snapshots()
    snaps["version"]["truncated"] = True
    snaps["endpoint:t3"]["code"] = 1
    report = lab.check_snapshots(snaps, expected())
    assert not report["checks"]["runtime_version"]
    assert not report["checks"]["endpoint_exists:t3"]


def test_reject_invalid_or_duplicated_tenant_registry(tmp_path):
    path = tmp_path / "tenants.json"
    invalid = (
        [{"tenant_id": "t1", "did": "5511900003333"}],
        [{"tenant_id": "../t3", "did": "5511900003333"}],
        [{"tenant_id": "t3", "did": "BAD"}],
        [{"tenant_id": "t3", "did": "5511900003333"}] * 2,
        [{"tenant_id": "t3", "did": "5511900003333"},
         {"tenant_id": "t4", "did": "5511900003333"}],
        {"tenant_id": "t3", "did": "5511900003333"},
    )
    for value in invalid:
        path.write_text(json.dumps(value))
        with pytest.raises(ValueError):
            lab.read_expected_tenants(path)
    path.write_text(json.dumps([{
        "tenant_id": "t3", "did": "5511900003333", "password": "SECRET"
    }]))
    assert lab.read_expected_tenants(path) == {"t3": "5511900003333"}


def test_symlink_registry_is_rejected(tmp_path):
    path = tmp_path / "real.json"
    path.write_text("[]")
    symlink = tmp_path / "tenants.json"
    symlink.symlink_to(path)
    with pytest.raises(ValueError):
        lab.read_expected_tenants(symlink)


def test_cli_uses_allowlisted_commands_and_no_shell():
    commands = lab.planned_commands(expected())
    seen = []
    def fake(argv, **kwargs):
        seen.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "Asterisk 22", "")
    with patch("asterisk_lab_audit.subprocess.run", side_effect=fake):
        result = lab.run_cli(commands)
    assert len(seen) == len(commands)
    for argv, kwargs in seen:
        assert argv[:5] == ["docker", "exec", "pabx-mvp", "asterisk", "-rx"]
        assert argv[5] in commands.values()
        assert kwargs["timeout"] == 8
        assert kwargs["check"] is False
        assert "shell" not in kwargs
    assert all(x["code"] == 0 for x in result.values())


def test_unsafe_container_or_command_cannot_execute():
    with patch("asterisk_lab_audit.subprocess.run") as process:
        with pytest.raises(ValueError):
            lab.run_cli(lab.planned_commands({}), container="pabx; echo unsafe")
        with pytest.raises(ValueError):
            lab.run_cli({"bad": "core stop now"})
        with pytest.raises(ValueError):
            lab.run_cli(lab.planned_commands({}), timeout=0)
        process.assert_not_called()


def test_command_timeout_reports_unavailable():
    with patch("asterisk_lab_audit.subprocess.run",
               side_effect=subprocess.TimeoutExpired("asterisk", 1)):
        results = lab.run_cli({"version": "core show version"})
    assert results["version"]["code"] is None
    assert not lab.check_snapshots(results, {})["ready_for_call_homologation"]


def test_cli_emits_only_sanitized_json(capsys, tmp_path):
    registry = tmp_path / "tenants.json"
    registry.write_text(json.dumps([
        {"tenant_id": "t3", "did": "5511900003333"}
    ]))
    with patch("asterisk_lab_audit.run_cli",
               return_value=snapshots({"t3": "5511900003333"})):
        code = lab.main(["--runtime", "local", "--tenant-registry", str(registry)])
    output = capsys.readouterr().out
    report = json.loads(output)
    assert code == 0
    assert report["runtime"] == "local"
    assert "5511900003333" not in output
    assert "Context:" not in output


def test_main_fails_when_live_asterisk_not_available(capsys):
    with patch("asterisk_lab_audit.run_cli", return_value={}):
        exit_code = lab.main(["--runtime", "local"])
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert not report["ready_for_call_homologation"]

def test_cli_can_bind_report_to_operator_declared_sha_without_verifying_deployment(capsys):
    with patch("asterisk_lab_audit.run_cli", return_value=snapshots({})):
        result = lab.main(["--runtime", "local", "--source-commit", "A" * 40])
    assert result == 0
    report = json.loads(capsys.readouterr().out)
    assert report["source_commit"] == "a" * 40
    assert report["source_commit_verified_by_this_tool"] is False


def test_cli_rejects_invalid_source_commit():
    with pytest.raises(SystemExit) as raised:
        lab.main(["--source-commit", "not-a-sha"])
    assert raised.value.code == 2
