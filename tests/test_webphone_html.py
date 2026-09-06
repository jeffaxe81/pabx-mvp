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
    "idleView", "incomingView", "activeView",
    "dialInput", "callBtn",
    "answerBtn", "declineBtn",
    "activePeer", "activeState", "callTimer",
    "muteBtn", "holdBtn", "hangupBtn",
    "transferTarget", "transferBtn",
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
