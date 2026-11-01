"""REL-10: auditoria de decisões sem exposição de números e segredos."""
from pathlib import Path

POLICY = (Path(__file__).resolve().parents[1] / "asterisk/dialplan_politica_externa.conf").read_text(encoding="utf-8")
SECTION = POLICY.split("[politica-externa]", 1)[1]


def test_decisoes_possuem_eventos_de_auditoria_distintos():
    assert "AUDIT_POLITICA_EXTERNA tenant=${TENANT} decisao=ALLOW" in SECTION
    assert "AUDIT_POLITICA_EXTERNA tenant=${TENANT} decisao=DENY" in SECTION
    assert SECTION.index("decisao=ALLOW") < SECTION.index("Return(ALLOW)")
    assert SECTION.index("decisao=DENY") < SECTION.index("Return(DENY)")


def test_auditoria_nao_expoe_destino_sip_ou_credenciais():
    for line in SECTION.splitlines():
        if "AUDIT_POLITICA_EXTERNA" in line:
            assert "${DESTINO}" not in line
            assert "CALLERID" not in line
            assert "PASSWORD" not in line
            assert "SECRET" not in line
            assert "DB(" not in line
