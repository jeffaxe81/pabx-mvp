import json

import pytest
from homologation_gate import SCENARIOS, main, summarize, to_markdown


def fixture_payload(status="pending", evidence=""):
    return {
        "schema_version": 1,
        "source_commit": "a" * 40,
        "checks": {
            key: {"status": status, "evidence": evidence}
            for key, _ in SCENARIOS
        },
    }


def test_pending_scenarios_block_go_and_show_zero_progress():
    report = summarize(fixture_payload())
    assert report["coverage_percent"] == 0.0
    assert report["counts"]["pending"] == 13
    assert report["gate_ready"] is False
    assert report["real_calls_executed_by_this_tool"] is False


def test_partial_approvals_update_percentage_without_go():
    payload = fixture_payload()
    for key, _ in SCENARIOS[:4]:
        payload["checks"][key] = {"status": "passed", "evidence": "LAB-2026-01"}
    report = summarize(payload)
    assert report["counts"]["passed"] == 4
    assert report["coverage_percent"] == 30.8
    assert not report["gate_ready"]


def test_full_approval_only_with_evidence_per_check():
    report = summarize(fixture_payload("passed", "LAB-2026-OK"))
    assert report["coverage_percent"] == 100.0
    assert report["gate_ready"]
    assert len(report["checks"]) == 13


def test_approval_without_evidence_is_rejected():
    with pytest.raises(ValueError, match="evidência"):
        summarize(fixture_payload("passed", ""))


def test_invalid_or_missing_scenarios_rejected():
    payload = fixture_payload()
    payload["checks"].pop("tenant_isolation")
    with pytest.raises(ValueError, match="13 cenários"):
        summarize(payload)
    payload = fixture_payload()
    payload["checks"]["fake_test"] = {"status": "passed", "evidence": "not real"}
    with pytest.raises(ValueError, match="13 cenários"):
        summarize(payload)


def test_invalid_sha_or_schema_rejected():
    payload = fixture_payload()
    payload["source_commit"] = "main"
    with pytest.raises(ValueError, match="SHA Git"):
        summarize(payload)
    payload = fixture_payload()
    payload["schema_version"] = 2
    with pytest.raises(ValueError, match="schema_version"):
        summarize(payload)


def test_control_characters_in_reference_fail_closed():
    payload = fixture_payload()
    payload["checks"]["did_known"]["evidence"] = "SECRETS\nTOKEN"
    with pytest.raises(ValueError, match="controle"):
        summarize(payload)


def test_blocked_and_failed_never_count_as_passed():
    payload = fixture_payload()
    payload["checks"]["failover"]["status"] = "blocked"
    payload["checks"]["recordings"]["status"] = "failed"
    report = summarize(payload)
    assert report["counts"]["blocked"] == 1
    assert report["counts"]["failed"] == 1
    assert not report["gate_ready"]


def test_markdown_escape_evidence_pipe():
    payload = fixture_payload("passed", "LAB-1|ASSINADO")
    md = to_markdown(summarize(payload))
    assert "LAB-1\\|ASSINADO" in md
    assert "APTO PARA REVISÃO DE GO" in md
    assert "não executa chamadas" in md


def test_cli_returns_nonzero_for_incomplete_and_zero_for_complete(tmp_path, capsys):
    file = tmp_path / "evidencia.json"
    file.write_text(json.dumps(fixture_payload()), encoding="utf-8")
    assert main(["--file", str(file)]) == 1
    assert json.loads(capsys.readouterr().out)["gate_ready"] is False
    file.write_text(json.dumps(fixture_payload("passed", "LAB-OK")), encoding="utf-8")
    assert main(["--file", str(file), "--format", "markdown"]) == 0
    assert "100.0%" in capsys.readouterr().out


def test_cli_rejects_symlink_and_malformed_json(tmp_path, capsys):
    target = tmp_path / "results.json"
    target.write_text("{bad json", encoding="utf-8")
    assert main(["--file", str(target)]) == 2
    link = tmp_path / "link.json"
    link.symlink_to(target)
    assert main(["--file", str(link)]) == 2
    assert "inválido" in capsys.readouterr().err
