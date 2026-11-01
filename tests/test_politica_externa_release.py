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


def test_politica_inicia_negada_ate_validacao():
    context = POLICY.split('[politica-externa]', 1)[1]
    assert context.index('Set(GOSUB_RETVAL=DENY)') < context.index('GotoIf(')


def test_rota_alternativa_normaliza_destino_antes_da_politica():
    start = DIALPLAN.index('exten => rota-alternativa,1')
    end = DIALPLAN.index('exten => 800,1', start)
    section = DIALPLAN[start:end]
    assert section.index('Set(DESTINO=${DESTINO:1})') < section.index('Gosub(politica-externa,s,1)')


def test_t1_valida_destino_original_antes_de_escolher_rota_alternativa():
    """O prefixo 00 do destino original nao pode escapar da politica."""
    start = DIALPLAN.index("[t1-internal]")
    end = DIALPLAN.index("exten => rota-alternativa,1", start)
    section = DIALPLAN[start:end]
    policy = section.index("Gosub(politica-externa,s,1)")
    route = section.index("?rota-alternativa,1)")
    assert policy < route
    assert section.index('GotoIf($["${GOSUB_RETVAL}" != "ALLOW"]?numero-bloqueado,1)', policy) < route


def test_politica_nao_permite_destino_invalido_antes_de_allow():
    context = POLICY.split("[politica-externa]", 1)[1]
    allow = context.index("Set(GOSUB_RETVAL=ALLOW)")
    assert context.index('GotoIf($["${DESTINO}" = ""]?negado)') < allow
    assert context.index('REGEX("^[0-9]+$" ${DESTINO})') < allow


def test_politica_internacional_consulta_tenant_corrente():
    context = POLICY.split("[politica-externa]", 1)[1]
    assert "DB(politica-externa-${TENANT}/internacional)" in context
    assert 'REGEX("^t[0-9]+$" ${TENANT})' in context
    assert context.index('REGEX("^t[0-9]+$" ${TENANT})') < context.index("DB(politica-externa-${TENANT}/internacional)")


def test_politica_nega_sem_tenant_antes_de_permitir():
    context = POLICY.split("[politica-externa]", 1)[1]
    assert context.index('GotoIf($["${TENANT}" = ""]?negado)') < context.index("Set(GOSUB_RETVAL=ALLOW)")


def test_politica_exige_decisao_negativa_por_padrao():
    context = POLICY.split("[politica-externa]", 1)[1]
    assert context.index("Set(GOSUB_RETVAL=DENY)") < context.index("Set(GOSUB_RETVAL=ALLOW)")


def test_politica_so_consulta_bloqueio_apos_identificar_prefixo_internacional():
    context = POLICY.split("[politica-externa]", 1)[1]
    assert context.index('DESTINO:0:2') < context.index('DB(politica-externa-${TENANT}/internacional)')


def test_politica_retorna_explicitamente_nos_dois_caminhos():
    context = POLICY.split("[politica-externa]", 1)[1]
    assert context.count("Return()") >= 2
    assert "n(negado),NoOp(" in context
    assert "n(permitido),Set(GOSUB_RETVAL=ALLOW)" in context


def test_rota_alternativa_usa_gateway_secundario_apos_autorizacao():
    start = DIALPLAN.index("exten => rota-alternativa,1")
    end = DIALPLAN.index("exten => 800,1", start)
    section = DIALPLAN[start:end]
    assert section.index('GotoIf($["${GOSUB_RETVAL}" != "ALLOW"]?numero-bloqueado,1)') < section.index("Dial(PJSIP/${DESTINO}@gateway-tdm-2,30)")


def test_tenant_t2_nao_seleciona_rota_alternativa_t1():
    start = DIALPLAN.index("[t2-internal]")
    end = DIALPLAN.find("\n[", start + 1)
    section = DIALPLAN[start:end if end >= 0 else None]
    assert "Gosub(politica-externa,s,1)" in section
    assert "gateway-tdm-2" not in section
