"""REL-03: auditoria 100/100 IDs com classificação sem novas features fictícias."""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_roadmap_auditoria_conservadora():
    original = (ROOT / "docs/roadmap-100-funcionalidades-candidatas.md").read_text(encoding="utf-8")
    expected = set(re.findall(r"AXEF-\d{4}", original))
    with (ROOT / "docs/rel03-auditoria-100-candidatos.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    ids = [row["id"] for row in rows]
    assert len(rows) == 100
    assert len(set(ids)) == 100
    assert set(ids) == expected
    allowed = {"EXISTENTE", "PARCIAL", "SEM_EVIDENCIA_DIRETA"}
    assert {r["classificacao"] for r in rows} == allowed
    assert all(r["referencia_comparada"].strip() for r in rows)
    assert all(len(r["conclusao"].strip()) > 25 for r in rows)
    assert all(r["funcionalidade"].strip() for r in rows)
