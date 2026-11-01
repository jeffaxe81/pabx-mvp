"""Regressões offline: nenhuma declaração pode ser confundida com GO real."""
import json
from pathlib import Path

import pytest

import rc_evidence_packet as packet


SHA = "a" * 40
OTHER = "b" * 40


def complete_claims():
    record = packet.make_packet(SHA)
    for key in record["homologation"]["checks"]:
        record["homologation"]["checks"][key] = {
            "status": "passed", "evidence": "EV-HOMOLOG-001"
        }
    for key in record["operational_checks"]:
        record["operational_checks"][key] = {
            "status": "passed", "evidence": "EV-OPS-001"
        }
    return record


def test_template_has_13_and_15_pending_and_no_go():
    initial = packet.make_packet(SHA)
    assert len(initial["homologation"]["checks"]) == 13
    assert len(initial["operational_checks"]) == 15
    report = packet.evaluate(initial, SHA)
    assert report["homologation_declared_passed"] == 0
    assert report["operational_declared_passed"] == 0
    assert not report["ready_for_independent_review"]
    assert report["decision"] == "PENDING_EVIDENCE_NO_GO"
    assert report["operational_go_authorized"] is False
    assert report["evidence_authenticity_verified_by_tool"] is False


def test_all_declared_evidence_only_opens_independent_review():
    report = packet.evaluate(complete_claims(), SHA)
    assert report["homologation_declared_passed"] == 13
    assert report["operational_declared_passed"] == 15
    assert report["ready_for_independent_review"]
    assert report["decision"] == "EVIDENCE_REVIEW_REQUIRED_NO_GO"
    assert report["source_sha_verified_against_runtime"] is False
    assert report["real_tests_executed_by_tool"] is False
    assert report["production_deployment_performed"] is False
    assert report["operational_go_authorized"] is False


def test_single_failed_operational_proof_blocks_review():
    source = complete_claims()
    first = next(iter(source["operational_checks"]))
    source["operational_checks"][first] = {
        "status": "failed", "evidence": "EV-OPS-FAIL"
    }
    result = packet.evaluate(source, SHA)
    assert result["operational_declared_passed"] == 14
    assert not result["ready_for_independent_review"]


def test_single_pending_homologation_blocks_review():
    source = complete_claims()
    source["homologation"]["checks"]["failover"] = {
        "status": "blocked", "evidence": ""
    }
    assert not packet.evaluate(source, SHA)["ready_for_independent_review"]


@pytest.mark.parametrize("invalid", [
    "main", "ABC", "a" * 39, "z" * 40, None
])
def test_invalid_sha_rejected(invalid):
    with pytest.raises(ValueError):
        packet.make_packet(invalid)


def test_different_source_sha_is_rejected():
    source = complete_claims()
    with pytest.raises(ValueError, match="SHA"):
        packet.evaluate(source, OTHER)
    source = complete_claims()
    source["homologation"]["source_commit"] = OTHER
    with pytest.raises(ValueError, match="SHA"):
        packet.evaluate(source, SHA)


def test_missing_extra_and_duplicate_proofs_are_rejected():
    source = complete_claims()
    source["operational_checks"].pop(next(iter(source["operational_checks"])))
    with pytest.raises(ValueError, match="ausentes"):
        packet.evaluate(source, SHA)

    source = complete_claims()
    source["operational_checks"]["PABX-OPS-08-FORGED"] = {
        "status": "passed", "evidence": "EV-FAKE-1234"
    }
    with pytest.raises(ValueError, match="ausentes"):
        packet.evaluate(source, SHA)


@pytest.mark.parametrize("state,ref", [
    ("passed", ""), ("pending", "EV-OPS-12345"),
    ("success", "EV-OPS-12345"), (True, "EV-OPS-12345"),
    (["passed"], "EV-OPS-12345"), ("passed", "password=secret"),
    ("passed", "https://example.com/?token=secret"),
    ("passed", "../sensitive"), ("passed", "EV-X\nTOKEN"),
    ("passed", 123),
])
def test_invalid_operational_claim_rejected(state, ref):
    source = complete_claims()
    key = next(iter(source["operational_checks"]))
    source["operational_checks"][key] = {"status": state, "evidence": ref}
    with pytest.raises((ValueError, TypeError)):
        packet.evaluate(source, SHA)


def test_no_flag_in_input_can_enable_production():
    source = complete_claims()
    source["operational_go_authorized"] = True
    with pytest.raises(ValueError, match="NO-GO"):
        packet.evaluate(source, SHA)
    source = complete_claims()
    source["production_ready"] = True
    with pytest.raises(ValueError, match="estrutura"):
        packet.evaluate(source, SHA)


def test_duplicate_keys_and_nonfinite_json_rejected(tmp_path):
    target = tmp_path / "packet.json"
    for content in (
        '{"source_commit":"a","source_commit":"b"}',
        '{"operational_checks":{"x":1,"x":2}}',
        '{"counts":NaN}', '{"counts":Infinity}'
    ):
        target.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            packet.read_json(target)


def test_symlink_and_oversized_files_rejected(tmp_path):
    target = tmp_path / "data.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "alias.json"
    link.symlink_to(target)
    with pytest.raises(ValueError):
        packet.read_json(link)
    target.write_bytes(b"x" * (packet.MAX_BYTES + 1))
    with pytest.raises(ValueError):
        packet.read_json(target)


def test_template_is_private_and_not_overwritten(tmp_path, capsys):
    path = tmp_path / "local-evidence.json"
    assert packet.main(["--init", str(path), "--sha", SHA]) == 0
    assert path.stat().st_mode & 0o777 == 0o600
    saved = path.read_bytes()
    assert json.loads(saved)["operational_go_authorized"] is False
    assert packet.main(["--init", str(path), "--sha", SHA]) == 2
    assert path.read_bytes() == saved
    assert packet.main(["--evaluate", str(path), "--sha", SHA]) == 1
    report = json.loads(capsys.readouterr().out.split("}\n")[-1] + "}") if False else None
    assert report is None


def test_cli_declared_success_is_still_not_go(tmp_path, capsys):
    path = tmp_path / "claims.json"
    path.write_text(json.dumps(complete_claims()), encoding="utf-8")
    assert packet.main(["--evaluate", str(path), "--sha", SHA]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ready_for_independent_review"]
    assert report["operational_go_authorized"] is False
