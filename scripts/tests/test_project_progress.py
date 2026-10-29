"""Avanco tecnico fracionado, sem alterar marcos de GO e homologacao."""
import copy
import json
from pathlib import Path

import pytest

from project_progress import ROOT, PLAN, CRITERIA, _read, calculate, main


def test_technical_progress_is_fifty_one_three_with_separate_formal_forty_three_eight():
    report = calculate(_read(PLAN), _read(CRITERIA))
    assert report["formal_completed"] == 7
    assert report["formal_total"] == 16
    assert report["formal_percent"] == 43.8
    assert report["technical_equivalent_units"] == 8.2
    assert report["technical_percent"] == 51.3
    assert report["partial_milestones"] == [
        {"week": 8, "verified": 3, "total": 5, "percent": 60.0},
        {"week": 9, "verified": 3, "total": 5, "percent": 60.0},
    ]
    assert not report["operational_go_authorized"]
    assert not report["technical_metric_is_operational_homologation"]
    assert all(m["status"] != "done" for m in _read(PLAN)["milestones"][7:9])


def test_status_of_pending_proof_cannot_be_forged_without_ci_reference():
    doc = _read(CRITERIA)
    for week in (8, 9):
        candidate = copy.deepcopy(doc)
        check = next(x for x in candidate["partial_milestones"]
                     if x["week"] == week)["criteria"][-1]
        check["state"] = "verified_lab"
        with pytest.raises(ValueError, match="prova"):
            calculate(_read(PLAN), candidate)


def test_progress_refuses_marking_done_and_partial_twice():
    plan = _read(PLAN)
    plan["milestones"][7]["status"] = "done"
    with pytest.raises(ValueError, match="marco parcial"):
        calculate(plan, _read(CRITERIA))


@pytest.mark.parametrize("status", ["operational", "verified", "success", True, None])
def test_unsupported_partial_statuses_fail_closed(status):
    data = _read(CRITERIA)
    data["partial_milestones"][0]["criteria"][0]["state"] = status
    with pytest.raises(ValueError, match="estado"):
        calculate(_read(PLAN), data)


def test_duplicate_or_invalid_evidence_rejected(tmp_path):
    valid = _read(CRITERIA)
    check = valid["partial_milestones"][0]["criteria"][0]
    check["evidence_file"] = "../secrets.txt"
    with pytest.raises(ValueError, match="inseguro"):
        calculate(_read(PLAN), valid)
    json_path = tmp_path / "evil.json"
    json_path.write_text('{"schema_version":1,"schema_version":2}')
    with pytest.raises(ValueError, match="duplicada"):
        _read(json_path)


def test_cli_publishes_both_metrics_without_go(capsys):
    assert main([]) == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["technical_percent"] == 51.3
    assert emitted["formal_percent"] == 43.8
    assert emitted["operational_go_authorized"] is False
