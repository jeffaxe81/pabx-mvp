"""Regressões de revisão apenas documental/estática de recursos parciais."""
import copy

import pytest

from partial_code_review import CODE_STATUS, OP_STATUS, read_register, validate


def current():
    return read_register()


def test_four_partial_scopes_have_code_evidence_but_no_operational_go():
    result = validate(current())
    assert result["total_code_scopes_reviewed"] == 4
    assert result["code_only_review_percent"] == 100
    assert result["pending_operational_review"] == 4
    assert result["full_functionality_homologated"] is False
    assert result["real_environment_tests_executed"] is False
    assert result["operational_go_authorized"] is False
    assert all(row["code_review"] == CODE_STATUS for row in result["items"])
    assert all(row["operational"] == OP_STATUS for row in result["items"])
    assert all(row["gaps_remaining"] >= 1 for row in result["items"])


@pytest.mark.parametrize("field", [
    "real_tests_executed_by_this_register",
    "production_deployed_by_this_register",
    "operational_go_authorized",
])
def test_unsupported_operational_claims_are_rejected(field):
    data = current()
    data[field] = True
    with pytest.raises(ValueError, match="operacional"):
        validate(data)


def test_cannot_approve_feature_without_gaps():
    data = current()
    data["items"][0]["pending_implementation"] = []
    with pytest.raises(ValueError, match="lacunas"):
        validate(data)


def test_cannot_assert_operational_homologation_for_any_partial():
    data = current()
    data["items"][0]["operational_status"] = "APPROVED_REAL"
    with pytest.raises(ValueError, match="indevidamente"):
        validate(data)


def test_fake_symbol_is_not_static_evidence():
    data = current()
    data["items"][1]["evidence"][0]["symbol"] = "this_symbol_does_not_exist"
    with pytest.raises(ValueError, match="nao existe"):
        validate(data)


def test_missing_unit_test_reference_fails_closed():
    data = current()
    data["items"][2]["existing_test_files"] = ["tests/test_nonexistent_provisioning.py"]
    with pytest.raises(ValueError, match="ausente"):
        validate(data)


def test_all_expected_partial_domains_are_required():
    data = current()
    data["items"] = data["items"][:-1]
    with pytest.raises(ValueError, match="incompletas"):
        validate(data)


def test_duplicate_domain_rejected():
    data = current()
    data["items"][1]["id"] = data["items"][0]["id"]
    with pytest.raises(ValueError, match="duplicada"):
        validate(data)


def test_source_path_traversal_is_rejected():
    data = current()
    data["items"][0]["evidence"][0]["path"] = "../outside.py"
    with pytest.raises(ValueError, match="inseguro"):
        validate(data)


def test_existing_test_reference_does_not_claim_test_execution():
    report = validate(current())
    assert report["existing_tests_executed_by_this_tool"] is False
