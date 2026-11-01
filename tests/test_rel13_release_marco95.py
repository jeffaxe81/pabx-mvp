"""Marco historico REL-13: seu aceite de 95% continua registrado apos RC."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_rel13_evidencia_permanece_e_95_foi_marco_historico():
    content = (ROOT / "docs/release-fechamento-20-entregas.md").read_text(encoding="utf-8")
    rows = [row for row in content.splitlines() if row.startswith("- [")]
    row = next(row for row in rows if row.startswith("- [x] **REL-13"))
    for evidence in ("PR #351", "PR #356", "21/21", "174/174", "REFER", "1103"):
        assert evidence in row
    for limitation in ("operadora externa", "produção", "áudio renegociado"):
        assert limitation in row
    assert "**Fechamento de 95%" in content
    assert "Resta REL-20" in content
    assert "operacional" in content
