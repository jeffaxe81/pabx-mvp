"""Pós-release: integridade documental sem afirmar homologação operacional."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA = "3496a5f6e168c95fe3c68e20c8cc45bceb3eb5c9"


def test_rc_handoff_preserva_tag_e_producao_bloqueada():
    text = (ROOT / "docs/releases/rc-0.1.0-rc.1-checklist.md").read_text(encoding="utf-8")
    assert SHA in text
    assert "v0.1.0-rc.1" in text
    assert "41338933528" in text and "41338933536" in text and "41338933447" in text
    assert "13096990316" in text
    assert "draft=true" in text and "prerelease=true" in text
    assert "Produção: NO-GO" in text
    assert "Nenhuma alteração nesta documentação modifica o commit da tag" in text
    assert "issue #173" in text


def test_operacional_continua_pendente_apesar_da_rc_20_de_20():
    checklist = (ROOT / "docs/release-fechamento-20-entregas.md").read_text(encoding="utf-8")
    assert "20/20 concluídas (100%)" in checklist
    homologacao = json.loads((ROOT / "docs/modelo-homologacao-pabx.json").read_text(encoding="utf-8"))
    assert homologacao["source_commit"] is None
    assert len(homologacao["checks"]) == 13
    assert all(x["status"] == "pending" and x["evidence"] == ""
               for x in homologacao["checks"].values())
    operacoes = json.loads(
        (ROOT / "docs/quality/provas-operacionais-diferidas.json").read_text(encoding="utf-8")
    )
    assert operacoes["operational_go_authorized"] is False
    assert len(operacoes["pending_checks"]) == 15
    assert all(x["status"] == "DEFERRED_NOT_EXECUTED" and x["evidence"] is None
               for x in operacoes["pending_checks"])
