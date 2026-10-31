"""Regressões estáticas inéditas para a política externa multiempresa.

Não substituem testes de chamadas SIP reais.
"""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
DIALPLAN = (ROOT / "asterisk" / "extensions.conf").read_text(encoding="utf-8")
POLICY = (ROOT / "asterisk" / "dialplan_politica_externa.conf").read_text(encoding="utf-8")


def test_politica_externa_incluida():
    assert "#include dialplan_politica_externa.conf" in DIALPLAN


def test_politica_externa_retorna_decisao_explicita():
    assert "Set(GOSUB_RETVAL=ALLOW)" in POLICY
    assert "Set(GOSUB_RETVAL=DENY)" in POLICY


def test_politica_externa_isola_familia_astdb():
    assert "politica-externa-${TENANT}/internacional" in POLICY


def test_politica_externa_valida_tenant():
    assert 'REGEX("^t[0-9]+$" ${TENANT})' in POLICY


def test_tenants_estaticos_validam_antes_do_tronco():
    for tenant in ("t1", "t2"):
        start = DIALPLAN.index(f"[{tenant}-internal]")
        end = DIALPLAN.find("\n[", start + 1)
        section = DIALPLAN[start:end if end >= 0 else None]
        policy_call = section.index("Gosub(politica-externa,s,1)")
        dial = section.index("Dial(PJSIP/${DESTINO}@gateway-tdm,30)")
        assert policy_call < dial


def test_rota_alternativa_nao_contorna_politica():
    start = DIALPLAN.index("exten => rota-alternativa,1")
    end = DIALPLAN.index("exten => 800,1", start)
    section = DIALPLAN[start:end]
    assert section.index("Gosub(politica-externa,s,1)") < section.index("Dial(PJSIP/${DESTINO}@gateway-tdm-2,30)")


def test_wizard_gera_validacao_antes_do_dial():
    source = (ROOT / "admin-api" / "tenants.py").read_text(encoding="utf-8")
    assert 'Gosub(politica-externa,s,1)' in source
    assert 'GotoIf($["${{GOSUB_RETVAL}}" != "ALLOW"]?numero-bloqueado,1)' in source
