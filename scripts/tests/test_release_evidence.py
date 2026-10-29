"""Gates de evidência: vincular SHA sem fabricar homologação real."""
import json

import pytest

import release_evidence as release
from homologation_gate import SCENARIOS


SHA = "a" * 40
OTHER_SHA = "b" * 40


def good_audit(sha=SHA):
    checks = {
        "runtime_version": True,
        "transport:transport-tls": True,
        "transport:transport-wss": True,
        "ingress_unknown_did_rejection": True,
        "endpoint_exists:t1": True,
        "endpoint_exists:t2": True,
        "endpoint_context:t1": True,
        "endpoint_context:t2": True,
        "dialplan_context:t1": True,
        "dialplan_context:t2": True,
    }
    return {
        "schema_version": 1, "kind": "running_asterisk_readonly_lab_audit",
        "source_commit": sha, "source_commit_verified_by_this_tool": False,
        "checks": checks, "passed": len(checks), "total": len(checks),
        "ready_for_call_homologation": True,
        "registration_verified": False, "sip_call_tested": False,
        "rtp_tested": False, "srtp_tested": False,
        "live_tenant_isolation_tested": False, "backup_restore_tested": False,
    }


def good_homologation(sha=SHA):
    return {
        "schema_version": 1, "source_commit": sha,
        "checks": {
            key: {"status": "passed", "evidence": "LAB-TEST-001"}
            for key, _ in SCENARIOS
        },
    }


def summarize(audit=None, gate=None, sha=SHA):
    return release.compile_release_report(
        sha, good_audit() if audit is None else audit,
        good_homologation() if gate is None else gate,
        "1" * 64, "2" * 64,
    )


def test_all_declared_checks_allow_only_review_never_production():
    output = summarize()
    assert output["review_ready"]
    assert output["human_scenarios_passed"] == 13
    assert output["decision"] == "APTO PARA REVISÃO HUMANA DE GO"
    assert output["artifact_authenticity_checked"] is False
    assert output["source_commit_verified_against_deployment"] is False
    assert output["real_calls_executed_by_this_tool"] is False
    assert output["operational_go_authorized"] is False
    assert "LAB-TEST-001" not in json.dumps(output)


def test_partial_manual_homologation_never_passes_review():
    homol = good_homologation()
    homol["checks"]["rtp_two_way"] = {"status": "blocked", "evidence": ""}
    result = summarize(gate=homol)
    assert result["human_scenarios_passed"] == 12
    assert not result["review_ready"]
    assert result["decision"] == "BLOQUEADO"


def test_failed_lab_check_blocks_even_if_manual_claims_all_passed():
    audit = good_audit()
    audit["checks"]["endpoint_context:t1"] = False
    audit["passed"] = 9
    audit["ready_for_call_homologation"] = False
    assert not summarize(audit=audit)["review_ready"]


def test_unequal_release_shas_are_invalid():
    with pytest.raises(ValueError, match="SHA"):
        summarize(audit=good_audit(OTHER_SHA))
    with pytest.raises(ValueError, match="SHA"):
        summarize(gate=good_homologation(OTHER_SHA))


@pytest.mark.parametrize("field", [
    "sip_call_tested", "srtp_tested", "registration_verified",
    "live_tenant_isolation_tested",
])
def test_readonly_audit_cannot_claim_real_call_testing(field):
    audit = good_audit()
    audit[field] = True
    with pytest.raises(ValueError):
        summarize(audit=audit)


def test_fake_success_counts_rejected():
    audit = good_audit()
    audit["passed"] = 12
    with pytest.raises(ValueError):
        summarize(audit=audit)


def test_missing_mandatory_lab_fields_fail_closed():
    audit = good_audit()
    del audit["checks"]["endpoint_context:t2"]
    audit["total"] = 9
    audit["passed"] = 9
    with pytest.raises(ValueError):
        summarize(audit=audit)


def test_no_empty_evidence_can_claim_passed_manual_scenario():
    gate = good_homologation()
    gate["checks"]["internal_call"]["evidence"] = ""
    with pytest.raises(ValueError):
        summarize(gate=gate)


def test_evidence_sha256_is_calculated_without_exposing_contents(tmp_path):
    path = tmp_path / "lab.json"
    path.write_text(json.dumps(good_audit()), encoding="utf-8")
    report, digest = release.read_report(path)
    assert report["kind"] == good_audit()["kind"]
    assert len(digest) == 64
    assert "tenant-did" not in digest


def test_evidence_symlink_and_large_file_rejected(tmp_path):
    target = tmp_path / "original.json"
    target.write_text("{}")
    link = tmp_path / "symlink.json"
    link.symlink_to(target)
    with pytest.raises(ValueError):
        release.read_report(link)
    target.write_bytes(b"x" * (release.MAX_EVIDENCE_BYTES + 1))
    with pytest.raises(ValueError):
        release.read_report(target)


def test_cli_reports_review_ready_and_blocked_without_go(tmp_path, capsys):
    audit_path = tmp_path / "lab.json"
    human_path = tmp_path / "manual.json"
    audit_path.write_text(json.dumps(good_audit()))
    human_path.write_text(json.dumps(good_homologation()))
    args = ["--sha", SHA, "--lab-audit", str(audit_path),
            "--homologation", str(human_path)]
    assert release.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["review_ready"]
    assert not result["operational_go_authorized"]
    manual = good_homologation()
    manual["checks"]["rtp_two_way"] = {"status": "pending", "evidence": ""}
    human_path.write_text(json.dumps(manual))
    assert release.main(args) == 1
    assert not json.loads(capsys.readouterr().out)["review_ready"]


def test_cli_invalid_report_has_error_exit_code(tmp_path, capsys):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text("{}")
    b.write_text("{}")
    assert release.main(["--sha", SHA, "--lab-audit", str(a),
                         "--homologation", str(b)]) == 2
    assert "inválidas" in capsys.readouterr().err

def test_release_evidence_rejects_duplicate_top_level_and_nested_keys(tmp_path):
    path = tmp_path / "untrusted.json"
    for raw in ('{"schema_version":1,"schema_version":1}',
                '{"checks":{"tenant_isolation":true,"tenant_isolation":false}}'):
        path.write_text(raw, encoding="utf-8")
        with pytest.raises(ValueError, match="duplicada"):
            release.read_report(path)
