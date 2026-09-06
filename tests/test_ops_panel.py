"""
Testes de regressão do webphone/painel-operacional.html (backlog #11
do documento de funcionalidades - painel em tempo real consolidado).
"""
from pathlib import Path

PANEL_HTML = Path(__file__).parent.parent / "webphone" / "painel-operacional.html"
WEBPHONE_HTML = Path(__file__).parent.parent / "webphone" / "index.html"

REQUIRED_IDS = ["metricsRow", "extensionsList", "queueList", "lastUpdate"]


def load_panel_html():
    return PANEL_HTML.read_text(encoding="utf-8")


def test_all_required_ids_present():
    html = load_panel_html()
    missing = [i for i in REQUIRED_IDS if f'id="{i}"' not in html]
    assert not missing, f"IDs esperados ausentes: {missing}"


def test_fetches_all_three_data_sources():
    html = load_panel_html()
    assert "/api/metrics/today" in html
    assert "/api/extension-states" in html
    assert "/api/queue" in html


def test_polls_periodically_for_supervision_use_case():
    """
    É um painel de parede/supervisão - precisa se atualizar sozinho,
    ninguém vai ficar apertando F5.
    """
    html = load_panel_html()
    assert "setInterval(fetchAll" in html


def test_api_url_is_configurable_via_query_param():
    """
    O painel precisa funcionar com a URL da API vinda por query string
    (?api=...), já que ele é aberto separado do console da telefonista.
    """
    html = load_panel_html()
    assert "URLSearchParams" in html
    assert "get('api')" in html


def test_operator_console_links_to_the_ops_panel():
    html = WEBPHONE_HTML.read_text(encoding="utf-8")
    assert 'id="opsPanelLink"' in html
    assert "painel-operacional.html" in html
