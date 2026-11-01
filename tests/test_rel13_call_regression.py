"""REL-13: regressões de dialplan para chamadas internas, externas e transferências.

Este teste verifica invariantes de configuração; não substitui chamadas SIP
com dois endpoints registrados e REFER/attended transfer em laboratório.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DIALPLAN = (ROOT / "asterisk/extensions.conf").read_text(encoding="utf-8")


def context(name):
    match = re.search(r"(?ms)^\[" + re.escape(name) + r"\]\n(.*?)(?=^\[|\Z)", DIALPLAN)
    assert match, f"contexto ausente: {name}"
    return match.group(1)


def extension_block(ctx, extension):
    section = context(ctx)
    match = re.search(
        r"(?ms)^exten => " + re.escape(extension)
        + r",1,.*?(?=^exten => |^#include |\Z)", section
    )
    assert match, f"ramal ausente: {ctx}/{extension}"
    return match.group(0)


def test_ramais_internos_nao_cruzam_tenants():
    for tenant in ("t1", "t2"):
        for ramal in ("1001",):
            block = extension_block(f"{tenant}-internal", ramal)
            assert f"Dial(PJSIP/{tenant}-{ramal}," in block
            assert f"VoiceMail({tenant}-{ramal}@{tenant}," in block
            other = "t2" if tenant == "t1" else "t1"
            assert f"PJSIP/{other}-" not in block


def test_saida_externa_passa_por_politica_e_bloqueio():
    for tenant in ("t1", "t2"):
        block = extension_block(f"{tenant}-internal", "_0.")
        assert f"DB(blocklist-{tenant}/" in block
        assert "Gosub(politica-externa,s,1)" in block
        assert 'GOSUB_RETVAL}' in block
        assert block.index("Gosub(politica-externa,s,1)") < block.index("Dial(PJSIP/")
        assert "gateway-tdm,30)" in block


def test_transferencia_inteligente_retorna_a_fila_do_mesmo_tenant():
    for tenant in ("t1", "t2"):
        for ramal in ("1010", "1011"):
            block = extension_block(f"{tenant}-internal", ramal)
            assert f"Dial(PJSIP/{tenant}-recepcao" in block
            assert "DIALSTATUS" in block
            assert f"Goto({tenant}-internal,1000,1)" in block


def test_rotas_de_transferencia_nao_inserem_outro_tenant():
    for tenant in ("t1", "t2"):
        for ramal in ("1010", "1011"):
            block = extension_block(f"{tenant}-internal", ramal)
            other = "t2" if tenant == "t1" else "t1"
            assert f"Goto({other}-internal" not in block
