"""Contrato mínimo da esteira de validação estática do AXE PABX."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "quality-gates.yml"

EXPECTED_SUITES = {
    ("configuracoes-web", "."),
    ("admin-api", "admin-api"),
    ("queue-api", "queue-api"),
    ("ai-worker", "ai-worker"),
    ("asterisk-agi", "asterisk/agi"),
    ("asterisk-scripts", "asterisk/scripts"),
    ("backup", "backup"),
    ("scripts", "scripts"),
}


def load_workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_ci_runs_on_main_and_pull_requests():
    workflow = load_workflow()
    triggers = workflow["on"]
    assert "pull_request" in triggers
    assert triggers["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in triggers


def test_ci_has_read_only_repository_permissions():
    workflow = load_workflow()
    assert workflow["permissions"] == {"contents": "read"}


def test_ci_matrix_includes_every_python_suite():
    workflow = load_workflow()
    job = workflow["jobs"]["static-tests"]
    included = job["strategy"]["matrix"]["include"]
    actual = {(entry["component"], entry["directory"]) for entry in included}
    assert actual == EXPECTED_SUITES
    assert job["strategy"]["fail-fast"] is False
    for _, directory in actual:
        assert (ROOT / directory / "tests").is_dir()


def test_ci_runs_pytest_from_each_component_directory():
    steps = load_workflow()["jobs"]["static-tests"]["steps"]
    commands = [step for step in steps if step.get("run") == "python -m pytest -q tests"]
    assert len(commands) == 1
    assert commands[0]["working-directory"] == "${{ matrix.directory }}"
    assert any("tests/requirements.txt" in step.get("run", "") for step in steps)
