"""
Testes estáticos do asterisk/extensions.conf.
"""
import re
from pathlib import Path

from conf_parser import parse_blocks, blocks_by_type

EXTENSIONS_CONF = Path(__file__).parent.parent / "asterisk" / "extensions.conf"
PJSIP_CONF = Path(__file__).parent.parent / "asterisk" / "pjsip.conf"

HINT_RE = re.compile(r"exten\s*=>\s*(\S+),hint,PJSIP/(\S+)")


def load_ext_blocks():
    return parse_blocks(EXTENSIONS_CONF)


def blocks_as_dict(blocks):
    """
    extensions.conf não usa herança de template como o pjsip.conf, mas
    o mesmo nome de contexto nunca deveria se repetir aqui - então um
    dict simples é seguro.
    """
    return {b["name"]: b["text"] for b in blocks}


def test_expected_contexts_present():
    contexts = {b["name"] for b in load_ext_blocks()}
    expected = {
        "t1-internal", "t2-internal", "t1-hints", "t2-hints",
        "from-tdm-gateway", "pickup-target", "click-to-call",
    }
    missing = expected - contexts
    assert not missing, f"Contextos esperados ausentes: {missing}"


def test_receptionist_extension_1000_routes_to_web_endpoint():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"].replace(" ", "")
    assert "exten=>1000,1,MixMonitor(" in text
    assert "Dial(PJSIP/t1-recepcao" in text


def test_unmatched_incoming_calls_go_into_the_queue():
    """
    Chamadas do gateway TDM sem DID mapeado entram na fila de
    atendimento (toca a telefonista se livre, espera se ocupada) -
    documentado no prompt master e no manual 08.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    fallback_block = blocks["from-tdm-gateway"]
    assert "_X." in fallback_block
    assert "Queue(fila-t1)" in fallback_block.replace(" ", "")


def test_pickup_target_context_dials_receptionist():
    """
    O contexto usado pelo pickup dirigido (Redirect via AMI) precisa
    realmente discar pro ramal da telefonista - senão o queue-api
    "puxa" a chamada da fila e ela cai no vazio.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    pickup_block = blocks["pickup-target"]
    assert "Dial(PJSIP/t1-recepcao" in pickup_block.replace(" ", "")


def test_receptionist_calls_are_recorded():
    """
    Os dois pontos onde a telefonista fala diretamente com alguém
    fora do fluxo de fila (dial direto no 1000, e a chamada puxada da
    fila) precisam gravar via MixMonitor - a fila em si já grava
    sozinha via monitor-type no queues.conf.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    assert "MixMonitor(" in blocks["t1-internal"]
    assert "MixMonitor(" in blocks["pickup-target"]


def test_click_to_call_context_dials_via_tdm_gateway():
    """
    O contexto usado pelo click-to-call (Originate via AMI, disparado
    pelo CRM) precisa realmente discar pro número do cliente através
    do tronco - senão o CRM "liga" e nada acontece do lado de fora.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    click_block = blocks["click-to-call"]
    assert "Dial(PJSIP/${EXTEN}@gateway-tdm" in click_block


def test_every_hint_references_an_endpoint_that_exists_in_pjsip_conf():
    """
    Todo 'hint,PJSIP/xxx' em extensions.conf precisa ter um endpoint
    'xxx' de verdade no pjsip.conf - senão o BLF simplesmente não
    funciona e ninguém percebe até testar na mão.
    """
    pjsip_blocks = parse_blocks(PJSIP_CONF)
    endpoint_names = {b["name"] for b in blocks_by_type(pjsip_blocks, "endpoint")}

    hint_targets = set()
    for block in load_ext_blocks():
        for match in HINT_RE.finditer(block["text"]):
            hint_targets.add(match.group(2))

    assert hint_targets, "Nenhum hint encontrado - verifique se o arquivo não quebrou"
    missing = hint_targets - endpoint_names
    assert not missing, f"Hints apontando para endpoints inexistentes: {missing}"


def test_tenants_do_not_share_extension_numbers_in_same_context():
    """
    Garante que dentro de um MESMO contexto de tenant não existem
    números de ramal duplicados (indicaria erro de copiar/colar entre
    tenants).
    """
    blocks = blocks_as_dict(load_ext_blocks())
    for context_name in ("t1-internal", "t2-internal"):
        text = blocks[context_name]
        extens = re.findall(r"exten\s*=>\s*(\d+),1,", text)
        assert len(extens) == len(set(extens)), (
            f"Números de ramal duplicados no contexto {context_name}: {extens}"
        )
