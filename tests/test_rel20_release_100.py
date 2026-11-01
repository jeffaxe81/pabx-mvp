"""Consistencia do estado final de engenharia de 20 marcos (REL-20)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_rc_local_versionado_com_20_de_20_e_sem_deploy():
    content = (ROOT / "docs/release-fechamento-20-entregas.md").read_text(encoding="utf-8")
    marks = [row for row in content.splitlines()
             if re.match(r"^- \[[ x]\] \*\*REL-[0-9]{2} —", row)]
    assert len(marks) == 20
    assert all(row.startswith("- [x]") for row in marks)
    assert "20/20 concluídas (100%)" in content
    assert "100% (20/20)" in content
    assert "0.1.0-rc.1" in marks[-1]
    assert "produção permanece NO-GO" in content
    assert "20/20" not in (ROOT / "VERSION").read_text(encoding="utf-8")
