"""
Testes de regressão do webphone/relatorios.html e do link a partir do
painel operacional.
"""
from pathlib import Path

REPORTS_HTML = Path(__file__).parent.parent / "webphone" / "relatorios.html"
OPS_PANEL_HTML = Path(__file__).parent.parent / "webphone" / "painel-operacional.html"

REQUIRED_IDS = [
    "startDate", "endDate", "groupBySelect", "generateBtn",
    "summaryContainer", "tableContainer",
]


def load_reports_html():
    return REPORTS_HTML.read_text(encoding="utf-8")


def test_all_required_ids_present():
    html = load_reports_html()
    missing = [i for i in REQUIRED_IDS if f'id="{i}"' not in html]
    assert not missing, f"IDs esperados ausentes: {missing}"


def test_group_by_options_match_backend_fields():
    """
    As opções do select precisam bater exatamente com os valores que
    o backend aceita em group_by (operator/tenant/date) - senão o
    filtro simplesmente não faz nada.
    """
    html = load_reports_html()
    assert 'value="operator"' in html
    assert 'value="tenant"' in html
    assert 'value="date"' in html


def test_requests_the_reports_endpoint_with_filters():
    html = load_reports_html()
    assert "/api/reports" in html
    assert "start" in html and "end" in html
    assert "group_by" in html


def test_api_url_is_configurable_via_query_param():
    html = load_reports_html()
    assert "URLSearchParams" in html
    assert "get('api')" in html


def test_ops_panel_links_to_reports_with_api_url_propagated():
    """
    O link do painel operacional pros relatórios precisa levar junto
    o endereço da API já configurado - senão a pessoa cai numa tela
    de relatórios sem saber pra qual servidor apontar.
    """
    html = OPS_PANEL_HTML.read_text(encoding="utf-8")
    assert 'id="reportsLink"' in html
    assert "relatorios.html?api=" in html
