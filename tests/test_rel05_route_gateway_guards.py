"""REL-05: a rota secundária não pode contornar autorização nem blocklist."""
from pathlib import Path

DIAL = (Path(__file__).resolve().parents[1] / "asterisk/extensions.conf").read_text(encoding="utf-8")


def section(start, end):
    return DIAL[DIAL.index(start):DIAL.index(end, DIAL.index(start))]


def test_rota_primaria_autoriza_destino_antes_de_selecionar_gateway():
    block = section("exten => _0.,1,Set(DESTINO=", "exten => numero-bloqueado,1")
    assert block.index("DB(blocklist-t1/${DESTINO})") < block.index("Gosub(politica-externa,s,1)")
    assert block.index('GOSUB_RETVAL') < block.index("rota-alternativa,1")
    assert block.index("rota-alternativa,1") < block.index("Dial(PJSIP/${DESTINO}@gateway-tdm,30)")


def test_rota_alternativa_revalida_destino_final_antes_do_tronco():
    block = section("exten => rota-alternativa,1", "exten => 800,1")
    assert block.index("Set(TENANT=t1)") < block.index("Set(DESTINO=${DESTINO:1})")
    assert block.index("Set(DESTINO=${DESTINO:1})") < block.index("DB(blocklist-t1/${DESTINO})")
    assert block.index("DB(blocklist-t1/${DESTINO})") < block.index("Gosub(politica-externa,s,1)")
    assert block.index("Gosub(politica-externa,s,1)") < block.index('GOSUB_RETVAL')
    assert block.index('GOSUB_RETVAL') < block.index("Dial(PJSIP/${DESTINO}@gateway-tdm-2,30)")


def test_rota_secundaria_nao_existe_no_contexto_t2():
    block = DIAL.split("[t2-internal]", 1)[1].split("\n[", 1)[0]
    assert "gateway-tdm-2" not in block
