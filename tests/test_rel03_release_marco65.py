"""Marco 65%: a auditoria documental é distinta de funcionalidades novas."""
from pathlib import Path
import csv


ROOT = Path(__file__).resolve().parents[1]


def test_rel03_marco_documentado_sem_contar_funcionalidade_nova():
    release = (ROOT / "docs/release-fechamento-20-entregas.md").read_text()
    assert "REL-03 — Auditoria de duplicidade" in release
    assert "65%" in release or "70%" in release
    assert "- [x] **REL-03" in release
    with (ROOT / "docs/rel03-auditoria-100-candidatos.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    assert len(rows) == 100
    from collections import Counter
    counts = Counter(row["classificacao"] for row in rows)
    assert counts == {"EXISTENTE": 6, "PARCIAL": 24, "SEM_EVIDENCIA_DIRETA": 70}
    assert "NOVA" not in counts
