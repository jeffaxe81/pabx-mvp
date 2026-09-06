"""
Testes estáticos do asterisk/extensions.conf.
"""
import re
from pathlib import Path

from conf_parser import parse_blocks, blocks_by_type

EXTENSIONS_CONF = Path(__file__).parent.parent / "asterisk" / "extensions.conf"
PJSIP_CONF = Path(__file__).parent.parent / "asterisk" / "pjsip.conf"

HINT_RE = re.compile(r"exten\s*=>\s*(\S+),hint,(\S+)")


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
    """
    Com múltiplas telefonistas (backlog #8), o ramal 1000 vira a
    entrada da fila (round-robin entre quem estiver logada), não mais
    um Dial() fixo pra uma única pessoa.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"].replace(" ", "")
    assert "exten=>1000,1,Queue(fila-t1)" in text


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
    ter uma entrada por telefonista - o Redirect especifica QUAL
    ramal deve receber a chamada puxada (backlog #8).
    """
    blocks = blocks_as_dict(load_ext_blocks())
    pickup_block = blocks["pickup-target"].replace(" ", "")
    assert "exten=>t1-recepcao,1," in pickup_block
    assert "Dial(PJSIP/t1-recepcao,20)" in pickup_block
    assert "exten=>t1-recepcao-2,1," in pickup_block
    assert "Dial(PJSIP/t1-recepcao-2,20)" in pickup_block


def test_admin_panel_dynamic_extensions_are_included():
    """
    Sem esses #include, os ramais criados pelo painel de administração
    (backlog #10) nunca aparecem no dialplan de verdade, mesmo que o
    admin-api tenha gerado o arquivo certinho.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    assert "#include extensions_dynamic_dial.conf" in blocks["t1-internal"]
    assert "#include extensions_dynamic_hints.conf" in blocks["t1-hints"]


def test_direct_operator_extensions_are_recorded():
    """
    Os ramais diretos de cada telefonista (1010/1011, uso interno da
    equipe) precisam gravar via MixMonitor, já que não passam pela
    fila (que grava sozinha via monitor-type).
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"]
    assert "1010" in text and "MixMonitor(" in text
    assert "1011" in text and "Dial(PJSIP/t1-recepcao-2" in text


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
    funciona e ninguém percebe até testar na mão. Hints combinados
    (ex: PJSIP/a&PJSIP/b, usados pra representar um grupo) são
    separados antes de checar cada dispositivo individualmente.
    """
    pjsip_blocks = parse_blocks(PJSIP_CONF)
    endpoint_names = {b["name"] for b in blocks_by_type(pjsip_blocks, "endpoint")}

    hint_targets = set()
    for block in load_ext_blocks():
        for match in HINT_RE.finditer(block["text"]):
            for device in match.group(2).split("&"):
                if device.startswith("PJSIP/"):
                    hint_targets.add(device[len("PJSIP/"):])

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
