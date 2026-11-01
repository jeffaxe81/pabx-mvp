"""Marco histórico REL-13 exige >=19 aceites e prova de telefonia real em sandbox."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_rel13_requer_ao_menos_19_aceites_e_evidencia_historica():
    content = (ROOT / "docs/release-fechamento-20-entregas.md").read_text(encoding="utf-8")
    lines = content.splitlines()
    marks = [line for line in lines if re.match(r"^- \[[ x]\] \*\*REL-[0-9]{2} —", line)]
    assert len(marks) == 20
    assert sum(line.startswith("- [x]") for line in marks) >= 19
    assert sum(line.startswith("- [ ]") for line in marks) <= 1
    assert any(line.startswith("- [x] **REL-20") for line in marks)
    assert any(line.startswith("- [x] **REL-13") for line in marks)
    assert "Fechamento de 95%" in content
    assert "100% (20/20)" in content


def test_rel13_distingue_transferencia_sip_real_de_homologacao_de_producao():
    content = (ROOT / "docs/release-fechamento-20-entregas.md").read_text(encoding="utf-8")
    row = next(line for line in content.splitlines() if line.startswith("- [x] **REL-13"))
    for evidence in ("PR #351", "PR #356", "21/21", "174/174", "REFER", "1103"):
        assert evidence in row
    for limitation in ("operadora externa", "produção", "áudio renegociado"):
        assert limitation in row
    assert "- [x] **REL-20" in content
