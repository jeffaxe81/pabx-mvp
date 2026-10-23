"""Programa de 16 semanas: validação de marcos sem inventar GO."""
import copy
import json
from pathlib import Path

import pytest

import program_progress


PLAN_PATH = Path(__file__).resolve().parents[2] / "docs" / "plano-16-semanas-pabx.json"


def plan():
    # Fixture de cálculo independente da evolução do status do plano versionado.
    source = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    for row in source['milestones']:
        row.update(status='planned', pr_number=None, ci_run_id=None)
    source['milestones'][0].update(status='done', pr_number=49, ci_run_id=39908454643)
    source['milestones'][1].update(status='done', pr_number=50, ci_run_id=39908954889)
    return source


def test_two_completed_milestones_report_12_5_percent():
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


def test_cli_json_and_markdown_show_same_progress(capsys, tmp_path):
    fixture = tmp_path/'program.json'
    fixture.write_text(json.dumps(plan()))
    assert program_progress.main(["--file", str(fixture)]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["program_percent"] == 12.5
    assert program_progress.main(["--file", str(fixture), "--format", "markdown"]) == 0
    markdown = capsys.readouterr().out
    assert "12.5%" in markdown
    assert "2/16" in markdown
    assert "GO" in markdown


def test_symlink_path_rejected(tmp_path, capsys):
    shortcut = tmp_path / "plan.json"
    shortcut.symlink_to(PLAN_PATH)
    assert program_progress.main(["--file", str(shortcut)]) == 2
    assert "simbólico" in capsys.readouterr().err


def test_multiple_milestones_in_same_pr_do_not_duplicate_completed_prs():
    source = plan()
    for row in source['milestones'][2:4]:
        row.update(status='done', pr_number=53, ci_run_id=39967937669)
    report = program_progress.summarize(source)
    assert report['weeks_completed'] == 4
    assert report['program_percent'] == 25.0
    assert report['completed_prs'] == [49, 50, 53]


def test_versioned_plan_has_sixteen_valid_acceptances_without_operational_go():
    versioned = json.loads(PLAN_PATH.read_text())
    assert len(program_progress.validate_plan(versioned)) == 16
    assert versioned['operational_go_authorized'] is False
