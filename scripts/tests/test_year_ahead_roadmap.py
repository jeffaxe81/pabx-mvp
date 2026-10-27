"""Contrato de antecipação: planejamento anual nunca vira aceite fictício."""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load():
    return json.loads((ROOT / "docs/roadmap-12-meses-pabx.json").read_text("utf-8"))


def test_roadmap_covers_exactly_a_year_and_all_pending_milestones():
    data = load()
    assert date.fromisoformat(data["horizon_start"]).isoformat() == "2026-10-23"
    assert (date.fromisoformat(data["horizon_end"])
            - date.fromisoformat(data["horizon_start"])).days == 365
    waves = data["waves"]
    assert len(waves) == 4
    assert [w["id"] for w in waves] == ["W1", "W2", "W3", "W4"]
    milestones = [m for w in waves for m in w["milestones"]]
    assert sorted(milestones) == list(range(8, 17))
    assert len(milestones) == len(set(milestones))
    assert all(w["acceptance"] and w["deliverables"] and w["dependencies"]
               for w in waves)


def test_roadmap_never_authorizes_go_or_counts_planning_as_completion():
    data = load()
    program = json.loads(
        (ROOT / "docs/plano-16-semanas-pabx.json").read_text("utf-8"))
    assert data["operational_go_authorized"] is False
    assert program["operational_go_authorized"] is False
    assert data["accepted_milestones_baseline"] == sum(
        x["status"] == "done" for x in program["milestones"])
    assert data["total_milestones"] == len(program["milestones"])
    assert data["accepted_milestones_baseline"] < data["total_milestones"]
    assert "evidencias" in data["completion_rule"]
    assert any(w["status"] == "in_progress" for w in data["waves"])
    assert all(w["status"] != "done" for w in data["waves"])
    assert data["cross_cutting_gates"] and all(
        g["blocking"] and g["status"] == "open"
        for g in data["cross_cutting_gates"])
