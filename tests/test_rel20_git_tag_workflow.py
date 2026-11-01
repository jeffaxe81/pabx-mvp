"""Complemento REL-20: tag da RC somente na main, nunca release GA."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_rc_tag_reflete_versionamento_ja_integrado():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    workflow = (ROOT / ".github/workflows/rel20-rc-tag.yml").read_text(encoding="utf-8")
    notes = (ROOT / "docs/releases/rc-0.1.0-rc.1-checklist.md").read_text(encoding="utf-8")
    assert version == "0.1.0-rc.1"
    assert "v0.1.0-rc.1" in notes
    assert "git tag -a" in workflow
    assert "git push origin" in workflow
    assert "scripts/rel20_rc_gate.py" in workflow
    assert "GITHUB_SHA" in workflow
    assert "branches:\n      - main" in workflow
    assert "--draft --prerelease --verify-tag" in workflow
    assert "contents: write" in workflow
    assert "latest" not in workflow.lower()
    assert "deploy" not in workflow.lower().split("run: |")[0]
