"""
Testes estáticos do asterisk/res_parking.conf (backlog #41 -
estacionamento de chamada). Não sobe o Asterisk de verdade - valida
que a configuração está estruturalmente correta e isolada por tenant.
"""
from pathlib import Path

from conf_parser import parse_blocks, get_key

RES_PARKING_CONF = Path(__file__).parent.parent / "asterisk" / "res_parking.conf"


def load_blocks():
    return parse_blocks(RES_PARKING_CONF)


def blocks_as_dict(blocks):
    return {b["name"]: b["text"] for b in blocks}


def test_parking_lots_exist_for_both_tenants():
    blocks = blocks_as_dict(load_blocks())
    assert "parkinglot-t1" in blocks
    assert "parkinglot-t2" in blocks


def test_each_parking_lot_uses_its_own_tenant_context():
    """
    Isolamento por tenant (manual 38): uma chamada estacionada no
    tenant 1 não pode aparecer pro tenant 2 - cada vaga vive dentro
    do próprio contexto interno do tenant.
    """
    blocks = blocks_as_dict(load_blocks())
    assert get_key(blocks["parkinglot-t1"], "context") == "t1-internal"
    assert get_key(blocks["parkinglot-t2"], "context") == "t2-internal"


def test_parking_lots_use_same_extension_numbers():
    """
    75/76-95 podem repetir entre tenants - contextos isolados, mesmo
    padrão de números já estabelecido pro resto do dialplan.
    """
    blocks = blocks_as_dict(load_blocks())
    for lot in ("parkinglot-t1", "parkinglot-t2"):
        assert get_key(blocks[lot], "parkext") == "75"
        assert get_key(blocks[lot], "parkpos") == "76-95"


def test_unretrieved_parked_call_rings_back_to_origin():
    """
    Sem isso, uma chamada estacionada e esquecida ficaria em silêncio
    pra sempre em vez de voltar pra quem estacionou.
    """
    blocks = blocks_as_dict(load_blocks())
    for lot in ("parkinglot-t1", "parkinglot-t2"):
        assert get_key(blocks[lot], "comebacktoorigin") == "yes"


def test_parking_hints_enabled_for_blf():
    """Sem isso, a telefonista não veria visualmente quais vagas estão ocupadas."""
    blocks = blocks_as_dict(load_blocks())
    for lot in ("parkinglot-t1", "parkinglot-t2"):
        assert get_key(blocks[lot], "parkinghints") == "yes"


def test_dynamic_parking_disabled_globally():
    """
    parkeddynamic=no de propósito - só as vagas explicitamente
    configuradas devem existir, nada implícito/automático que
    poderia vazar entre tenants.
    """
    blocks = blocks_as_dict(load_blocks())
    assert get_key(blocks["general"], "parkeddynamic") == "no"


def test_includes_wizard_created_tenant_parking_lots_via_wildcard():
    """Backlog #39/#41: tenant novo ganha vaga de estacionamento automaticamente, sem editar este arquivo."""
    content = RES_PARKING_CONF.read_text(encoding="utf-8")
    assert "#include parking_tenants/*.conf" in content
