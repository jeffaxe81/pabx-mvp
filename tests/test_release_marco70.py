"""Marco histórico de 70% preservado, inclusive após fechamento da RC."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_checklist_70_nao_confunde_sandbox_com_producao():
    text = (ROOT / "docs/release-fechamento-20-entregas.md").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.startswith("- [")]
    assert len(lines) == 20
    assert sum(line.startswith("- [x]") for line in lines) >= 14
    assert "70%" in text and "Fechamento de 70%" in text
    assert "- [x] **REL-17" in text
    assert "- [x] **REL-20" in text
    assert "100% (20/20)" in text
    assert "GO operacional: BLOQUEADO" in text
    assert "volumes Docker efêmeros" in text
    assert "não autorizam produção" in text
