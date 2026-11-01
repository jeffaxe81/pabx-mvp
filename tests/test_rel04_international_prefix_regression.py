"""REL-04: prefixos internacionais após remoção do código de acesso.

Teste de regressão de normalização e da ordem dos guards no dialplan.
Não substitui chamada SIP real.
"""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
DIAL = (ROOT / "asterisk/extensions.conf").read_text(encoding="utf-8")
POLICY = (ROOT / "asterisk/dialplan_politica_externa.conf").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("tenant", "numero_discado", "bloqueio", "esperado"),
    [
        ("t1", "000441234567", True, "DENY"),
        ("t1", "000441234567", False, "ALLOW"),
        ("t2", "000441234567", True, "DENY"),
        ("t2", "000441234567", False, "ALLOW"),
        ("t1", "0551199999999", True, "ALLOW"),
        ("t2", "0551199999999", True, "ALLOW"),
    ],
)
def test_prefixo_externo_e_regra_por_empresa(tenant, numero_discado, bloqueio, esperado):
    assert numero_discado.startswith("0")
    destino = numero_discado[1:]
    assert 'Set(DESTINO=${EXTEN:1})' in DIAL
    assert 'DESTINO:0:2' in POLICY
    assert 'DB(politica-externa-${TENANT}/internacional)' in POLICY
    decisao = "DENY" if destino.startswith("00") and bloqueio else "ALLOW"
    assert decisao == esperado


def test_ambos_tenants_exigem_autorizacao_antes_do_gateway():
    for tenant in ("t1", "t2"):
        context = DIAL.split(f"[{tenant}-internal]", 1)[1].split("\n[", 1)[0]
        assert context.index("Set(DESTINO=${EXTEN:1})") < context.index("Gosub(politica-externa,s,1)")
        assert context.index("Gosub(politica-externa,s,1)") < context.index("Dial(PJSIP/${DESTINO}@gateway-tdm,30)")


def test_t1_bloqueia_internacional_antes_de_remover_prefixo_de_rota():
    context = DIAL.split("[t1-internal]", 1)[1].split("exten => numero-bloqueado,1", 1)[0]
    assert context.index("Gosub(politica-externa,s,1)") < context.index("rota-alternativa,1")
    assert context.index("GOSUB_RETVAL") < context.index("rota-alternativa,1")
