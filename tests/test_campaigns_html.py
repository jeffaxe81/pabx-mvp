"""
Testes de regressão do webphone/campanhas.html.
"""
from pathlib import Path

CAMPAIGNS_HTML = Path(__file__).parent.parent / "webphone" / "campanhas.html"

REQUIRED_IDS = [
    "campaignApiKey", "campaignName", "campaignAgent", "campaignContacts",
    "createCampaignBtn", "createCampaignError",
    "campaignsList", "refreshCampaignsBtn",
    "callbacksList", "refreshCallbacksBtn",
]


def load_html():
    return CAMPAIGNS_HTML.read_text(encoding="utf-8")


def test_all_required_ids_present():
    html = load_html()
    missing = [i for i in REQUIRED_IDS if f'id="{i}"' not in html]
    assert not missing, f"IDs esperados ausentes: {missing}"


def test_requests_send_the_api_key_header():
    """
    Sem o header, toda chamada à API de campanhas falharia com 403 -
    confirma que o helper central sempre inclui a chave.
    """
    html = load_html()
    fn_start = html.index("function apiFetch")
    fn_end = html.index("});", fn_start)
    body = html[fn_start:fn_end]
    assert "X-Click-To-Call-Key" in body
    assert "apiKey()" in body


def test_api_url_is_configurable_via_query_param():
    html = load_html()
    assert "URLSearchParams" in html
    assert "get('api')" in html


def test_contacts_textarea_parsed_one_number_per_line():
    html = load_html()
    fn_start = html.index("el('createCampaignBtn').addEventListener")
    fn_end = html.index("});", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "split('\\n')" in body


def test_callback_panel_excludes_finished_statuses():
    """
    A lista de retornos pendentes precisa filtrar os já concluídos/
    esgotados/cancelados - senão a telefonista vê uma lista cheia de
    coisa que já foi resolvida, sem saber o que ainda falta discar.
    """
    html = load_html()
    fn_start = html.index("function renderCallbacks")
    fn_end = html.index("}", html.index("dialNextCallbackBtn", fn_start))
    body = html[fn_start:fn_end]
    assert "'concluido'" in body
    assert "'esgotado'" in body
    assert "'cancelado'" in body


def test_dial_next_callback_uses_correct_endpoint():
    html = load_html()
    assert "/api/callbacks/dial-next" in html
