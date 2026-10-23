"""Programa de 16 semanas: validação de marcos sem inventar GO."""
import copy
import json
from pathlib import Path

import pytest

import program_progress


PLAN_PATH = Path(__file__).resolve().parents[2] / "docs" / "plano-16-semanas-pabx.json"


def plan():
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def test_current_program_reports_only_two_completed_milestones():
    report = program_progress.summarize(plan())
    assert report["weeks_completed"] == 2
    assert report["program_percent"] == 12.5
    assert report["completed_prs"] == [49, 50]
    assert report["months"][0]["percent"] == 50.0
    assert all(m["percent"] == 0 for m in report["months"][1:])
    assert not report["operational_go_authorized"]
    assert not report["real_sip_calls_executed_by_this_tool"]


def test_16_weeks_and_month_boundaries_are_complete():
    rows = program_progress.validate_plan(plan())
    assert len(rows) == 16
    assert sorted(row["week"] for row in rows) == list(range(1, 17))
    assert [sum(x["month"] == month for x in rows) for month in range(1, 5)] == [4] * 4


@pytest.mark.parametrize("bad_status", ["complete", "", True, None])
def test_unknown_status_is_rejected(bad_status):
    source = plan()
    source["milestones"][3]["status"] = bad_status
    with pytest.raises(ValueError):
        program_progress.summarize(source)


def test_completed_milestone_requires_real_pr_number_and_ci_identifier():
    source = plan()
    source["milestones"][2]["status"] = "done"
    with pytest.raises(ValueError, match="PR"):
        program_progress.summarize(source)
    source["milestones"][2]["pr_number"] = 51
    source["milestones"][2]["ci_run_id"] = 123456
    assert program_progress.summarize(source)["weeks_completed"] == 3


def test_future_milestone_cannot_claim_completed_pr_and_ci():
    source = plan()
    source["milestones"][2]["pr_number"] = 51
    with pytest.raises(ValueError):
        program_progress.summarize(source)


def test_repeated_week_or_wrong_month_rejected():
    source = plan()
    source["milestones"][2]["week"] = 2
    with pytest.raises(ValueError):
        program_progress.summarize(source)
    source = plan()
    source["milestones"][4]["month"] = 1
    with pytest.raises(ValueError):
        program_progress.summarize(source)


def test_go_cannot_be_implicitly_authorized():
    source = plan()
    source["operational_go_authorized"] = True
    with pytest.raises(ValueError):
        program_progress.summarize(source)


def test_control_characters_in_title_rejected():
    source = plan()
    source["milestones"][4]["title"] = "Chamada\nBad"
    with pytest.raises(ValueError):
        program_progress.summarize(source)


def test_cli_json_and_markdown_show_same_progress(capsys):
    assert program_progress.main(["--file", str(PLAN_PATH)]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["program_percent"] == 12.5
    assert program_progress.main(["--file", str(PLAN_PATH), "--format", "markdown"]) == 0
    markdown = capsys.readouterr().out
    assert "12.5%" in markdown
    assert "2/16" in markdown
    assert "GO" in markdown


def test_symlink_path_rejected(tmp_path, capsys):
    shortcut = tmp_path / "plan.json"
    shortcut.symlink_to(PLAN_PATH)
    assert program_progress.main(["--file", str(shortcut)]) == 2
    assert "simbólico" in capsys.readouterr().err
