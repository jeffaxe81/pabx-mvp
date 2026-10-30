"""Checagem estática do cadastro; não executa provas operacionais."""
import copy
import json
from pathlib import Path

import pytest

from operational_proofs_deferred import (
    DEFAULT_PLAN, DEFAULT_REGISTER, main, read_json, summarize,
)


def sources():
    return json.loads(DEFAULT_REGISTER.read_text(encoding="utf-8")), json.loads(
        DEFAULT_PLAN.read_text(encoding="utf-8")
    )


def test_registered_deferral_preserves_development_and_blocks_go():
    register, plan = sources()
    report = summarize(register, plan)
    assert report["registered_pending_checks"] == 15
    assert report["affected_milestones"] == list(range(8, 17))
    assert report["executed_operational_proofs"] == 0
    assert report["formal_milestones_done"] == 7
    assert report["formal_percent"] == 43.8
    assert report["development_can_continue"] is True
    assert report["controlled_real_environment_homologation_allowed"] is True
    assert report["unproven_code_status"] == "CODE_REGISTERED_PENDING_REAL_HOMOLOGATION"
    assert report["pending_real_environment_homologations"] == 15
    assert report["target_preflight_and_rollback_required"] is True
    assert report["automated_ci_still_required"] is True
    assert report["homologation_complete"] is False
    assert report["operational_go_authorized"] is False


@pytest.mark.parametrize("field,value", [
    ("operational_proofs_executed_in_this_change", True),
    ("operational_go_authorized", True),
    ("ci_security_gates_must_remain_enabled", False),
])
def test_no_claim_of_execution_and_no_disable_ci(field, value):
    register, plan = sources()
    register[field] = value
    with pytest.raises(ValueError):
        summarize(register, plan)


@pytest.mark.parametrize("field,value", [
    ("status", "PASSED"), ("evidence", "fake-artifact"),
    ("executed_at", "2026-10-29T17:00:00Z"), ("approved_at", "now"),
])
def test_deferred_check_cannot_claim_evidence_or_approval(field, value):
    register, plan = sources()
    register["pending_checks"][0][field] = value
    with pytest.raises(ValueError):
        summarize(register, plan)


def test_reject_duplicate_ids_and_mismatched_milestones():
    register, plan = sources()
    register["pending_checks"][1]["id"] = register["pending_checks"][0]["id"]
    with pytest.raises(ValueError):
        summarize(register, plan)
    register, plan = sources()
    register["pending_checks"][0]["milestone_week"] = 9
    with pytest.raises(ValueError):
        summarize(register, plan)


def test_marking_deferred_stage_done_requires_removing_pending_record():
    register, plan = sources()
    stage = next(m for m in plan["milestones"] if m["week"] == 8)
    stage["status"] = "done"
    with pytest.raises(ValueError, match="concluido"):
        summarize(register, plan)


def test_release_approval_flag_remains_false():
    register, plan = sources()
    plan["operational_go_authorized"] = True
    with pytest.raises(ValueError):
        summarize(register, plan)


def test_invalid_external_json_cannot_override_pending_status(tmp_path):
    file = tmp_path / "ambiguous.json"
    raw = DEFAULT_REGISTER.read_text(encoding="utf-8")
    raw = raw.replace('"status": "DEFERRED_NOT_EXECUTED"',
                      '"status": "DEFERRED_NOT_EXECUTED", "status": "PASSED"', 1)
    file.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicadas"):
        read_json(file)


def test_cli_reports_deferred_not_completed(capsys):
    assert main([]) == 0
    result = json.loads(capsys.readouterr().out)
    assert not result["homologation_complete"]
    assert not result["operational_go_authorized"]


@pytest.mark.parametrize("field,value", [
    ("controlled_application_allowed_for_homologation", False),
    ("unproven_code_status", "HOMOLOGATED"),
    ("record_missing_evidence_without_claiming_approval", False),
    ("automated_code_and_security_ci_required", False),
    ("target_environment_preflight_and_rollback_required", False),
    ("production_go_requires_separate_explicit_acceptance", False),
])
def test_real_homologation_policy_is_explicit_and_fail_closed(field, value):
    register, plan = sources()
    register["real_environment_policy"][field] = value
    with pytest.raises(ValueError, match="politica"):
        summarize(register, plan)


def test_real_environment_candidate_never_grants_go_or_evidence():
    register, plan = sources()
    report = summarize(register, plan)
    assert report["controlled_real_environment_homologation_allowed"] is True
    assert report["executed_operational_proofs"] == 0
    assert report["operational_go_authorized"] is False
    assert report["homologation_complete"] is False


@pytest.mark.parametrize("field,value", [
    ("homologation_required", False),
    ("target_environment", "PRODUCTION_APPROVED"),
])
def test_pending_checks_always_require_real_homologation(field, value):
    register, plan = sources()
    register["pending_checks"][0][field] = value
    with pytest.raises(ValueError, match="homologacao"):
        summarize(register, plan)


def test_plan_must_match_real_homologation_classification():
    register, plan = sources()
    plan["development_policy"]["controlled_real_environment_homologation_permitted"] = False
    with pytest.raises(ValueError, match="politica"):
        summarize(register, plan)
