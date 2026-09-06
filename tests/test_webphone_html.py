"""
Testes de regressão do webphone/index.html.

Não substituem teste manual num navegador real (isso fica documentado
em docs/manual-05-telefonista-web.md), mas evitam que uma edição
futura remova sem querer um id usado pelo JavaScript, quebrando a
interface silenciosamente.
"""
import re
from pathlib import Path

WEBPHONE_HTML = Path(__file__).parent.parent / "webphone" / "index.html"

REQUIRED_IDS = [
    "wssUrl", "extNumber", "extPassword", "connectBtn", "disconnectBtn",
    "statusDot", "statusText",
    "idleView", "incomingView", "activeView", "consultView",
    "dialInput", "callBtn",
    "answerBtn", "declineBtn",
    "activePeer", "activeState", "callTimer",
    "muteBtn", "holdBtn", "hangupBtn",
    "transferTarget", "transferBtn", "consultBtn",
    "consultHeldPeer", "consultTargetPeer", "consultTargetState",
    "cancelConsultBtn", "completeConsultBtn",
    "callLog", "colleaguesPanel", "colleaguesList",
    "remoteAudio",
]


def load_html():
    return WEBPHONE_HTML.read_text(encoding="utf-8")


def test_all_required_ids_present():
    html = load_html()
    missing = [i for i in REQUIRED_IDS if f'id="{i}"' not in html]
    assert not missing, f"IDs esperados ausentes no HTML: {missing}"


def test_jssip_library_is_loaded():
    html = load_html()
    assert "jssip" in html.lower()


def test_no_leftover_template_syntax():
    """Sanity check simples contra edição futura que deixe {{...}} solto."""
    html = load_html()
    assert not re.search(r"\{\{\w+\}\}", html)


def test_colleagues_config_array_exists():
    html = load_html()
    assert "const COLLEAGUES" in html, (
        "Array COLLEAGUES não encontrado - a lista de presença dos "
        "colegas depende dele"
    )


def test_assisted_transfer_uses_hold_before_consulting():
    """
    Transferência assistida precisa colocar a chamada original em
    espera (hold) antes de discar pro colega - senão o chamador
    escutaria a consulta acontecendo.
    """
    html = load_html()
    consult_click_start = html.index("el('consultBtn').addEventListener")
    consult_click_end = html.index("});", consult_click_start)
    handler_body = html[consult_click_start:consult_click_end]
    assert "primarySession.hold()" in handler_body


def test_assisted_transfer_completion_sends_refer_and_cleans_up_both_legs():
    """
    Completar a transferência assistida precisa: mandar o REFER pra
    chamada original, e encerrar tanto a chamada original quanto a de
    consulta do lado da telefonista (senão as duas pernas ficam penduradas).
    """
    html = load_html()
    complete_start = html.index("el('completeConsultBtn').addEventListener")
    complete_end = html.index("function handleConsultEnded", complete_start)
    handler_body = html[complete_start:complete_end]

    assert "primarySession.refer(" in handler_body
    assert "primaryToClean.terminate()" in handler_body
    assert "peerToClean.terminate()" in handler_body


def test_consult_call_does_not_get_rejected_as_second_call():
    """
    A ligação de consulta é uma segunda sessão SIP de propósito -
    handleNewSession precisa reconhecer isso via expectingConsultCall
    ANTES de cair na regra geral que rejeita uma segunda chamada.
    """
    html = load_html()
    handler_start = html.index("function handleNewSession")
    reject_rule_pos = html.index("já em chamada", handler_start)
    consult_check_pos = html.index("expectingConsultCall && session.direction", handler_start)
    assert consult_check_pos < reject_rule_pos, (
        "A checagem de chamada de consulta precisa vir antes da regra "
        "que rejeita a segunda chamada"
    )
