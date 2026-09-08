"""
Testes de regressão do webphone/painel-operacional.html (backlog #11
do documento de funcionalidades - painel em tempo real consolidado).
"""
from pathlib import Path

PANEL_HTML = Path(__file__).parent.parent / "webphone" / "painel-operacional.html"
WEBPHONE_HTML = Path(__file__).parent.parent / "webphone" / "index.html"

REQUIRED_IDS = ["metricsRow", "extensionsList", "queueList", "lastUpdate", "fraudAlertsList", "qualityList", "slaList", "pauseHistoryList", "slaHistoryList",
                "pauseHistoryStart", "pauseHistoryEnd", "filterPauseHistoryBtn", "clearPauseHistoryBtn",
                "slaHistoryStart", "slaHistoryEnd", "filterSlaHistoryBtn", "clearSlaHistoryBtn"]


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


def test_fetches_fraud_alerts_too():
    html = load_panel_html()
    assert "/api/fraud-alerts" in html
    assert "renderFraudAlerts" in html


def test_fetches_quality_reports_filtered_to_poor_only():
    """
    O painel operacional pede só os relatórios RUINS (only_poor=true)
    - senão a lista ficaria poluída de chamadas com qualidade normal,
    que não é o que interessa numa tela de supervisão.
    """
    html = load_panel_html()
    assert "/api/quality?only_poor=true" in html
    assert "renderQuality" in html


def test_extensions_display_prioritizes_manual_presence_over_automatic_blf():
    """
    Se a telefonista marcou "férias" manualmente, isso precisa
    aparecer em vez do estado automático do BLF (que provavelmente
    mostraria "indisponível" ou algo sem contexto nenhum).
    """
    html = load_panel_html()
    fn_start = html.index("function renderExtensions")
    fn_end = html.index("}", html.index("dotClass = e.status_label", fn_start))
    body = html[fn_start:fn_end]
    assert "e.manual_status" in body


def test_pause_reason_has_highest_display_priority():
    """
    Backlog #44: pausa da fila é o estado mais operacional (afeta se
    a pessoa recebe chamada agora) - precisa ser checado ANTES até da
    presença manual.
    """
    html = load_panel_html()
    fn_start = html.index("function renderExtensions")
    pause_check_pos = html.index("e.pause_reason", fn_start)
    manual_status_pos = html.index("e.manual_status", fn_start)
    assert pause_check_pos < manual_status_pos


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


# ---------- SLA de fila (backlog #46) ----------

def test_sla_endpoint_is_fetched_and_rendered():
    html = load_panel_html()
    assert "/api/metrics/sla" in html
    assert "renderSla(" in html


def test_sla_display_shows_percentage_threshold_and_raw_counts():
    """
    Um percentual sozinho ("75%") não diz muito sem o contexto do
    limiar e dos números absolutos - a interface precisa mostrar os
    três juntos.
    """
    html = load_panel_html()
    fn_start = html.index("function renderSla(")
    fn_end = html.index("}\n\n", fn_start)
    body = html[fn_start:fn_end]
    assert "sla_percent" in body
    assert "threshold_seconds" in body
    assert "within_sla" in body
    assert "offered" in body


def test_sla_handles_empty_state_without_crashing():
    html = load_panel_html()
    fn_start = html.index("function renderSla(")
    fn_end = html.index("}\n\n", fn_start)
    body = html[fn_start:fn_end]
    assert "queues.length === 0" in body


# ---------- Histórico de pausa por motivo (backlog #57) ----------

def test_pause_history_endpoint_is_fetched_and_rendered():
    html = load_panel_html()
    assert "/api/reports/pauses" in html
    assert "renderPauseHistory(" in html


def test_pause_history_sorted_by_time_descending():
    """O motivo com mais tempo acumulado deveria aparecer primeiro - é a informação mais relevante."""
    html = load_panel_html()
    fn_start = html.index("function renderPauseHistory")
    fn_end = html.index("}\n\n", fn_start) if "}\n\n" in html[fn_start:] else html.index("}\n})", fn_start)
    body = html[fn_start:fn_end]
    assert ".sort(" in body


def test_pause_history_handles_empty_state_without_crashing():
    html = load_panel_html()
    fn_start = html.index("function renderPauseHistory")
    fn_end = html.index("}\n\n", fn_start) if "}\n\n" in html[fn_start:] else html.index("}\n})", fn_start)
    body = html[fn_start:fn_end]
    assert "byReason.length===0" in body.replace(" ", "")


# ---------- Histórico de SLA no painel (backlog #59) ----------

def test_sla_history_endpoint_is_fetched_and_rendered():
    html = load_panel_html()
    assert "/api/metrics/sla/history" in html
    assert "renderSlaHistory(" in html


def test_sla_history_sorted_most_recent_first():
    html = load_panel_html()
    fn_start = html.index("function renderSlaHistory")
    fn_end = html.index("}\n\n", fn_start) if "}\n\n" in html[fn_start:] else html.index("}\n})", fn_start)
    body = html[fn_start:fn_end]
    assert ".sort(" in body


def test_sla_history_handles_empty_state_without_crashing():
    html = load_panel_html()
    fn_start = html.index("function renderSlaHistory")
    fn_end = html.index("}\n\n", fn_start) if "}\n\n" in html[fn_start:] else html.index("}\n})", fn_start)
    body = html[fn_start:fn_end]
    assert "dates.length===0" in body.replace(" ", "")


# ---------- Filtro de intervalo de datas nos históricos (backlog #63) ----------

def test_history_filters_persist_across_polling_cycles():
    """
    O filtro precisa ser mantido em variável FORA de fetchAll() - se
    ficasse local à função, seria perdido a cada ciclo automático de
    atualização do painel.
    """
    html = load_panel_html()
    fetch_all_pos = html.index("function fetchAll")
    filter_var_pos = html.index("let pauseHistoryFilter")
    assert filter_var_pos < fetch_all_pos


def test_pause_history_fetch_includes_filter_query_params():
    html = load_panel_html()
    fn_start = html.index("function fetchAll")
    fn_end = html.index("}\n\n", fn_start)
    body = html[fn_start:fn_end]
    assert "buildHistoryQuery(pauseHistoryFilter)" in body


def test_sla_history_fetch_includes_filter_query_params():
    html = load_panel_html()
    fn_start = html.index("function fetchAll")
    fn_end = html.index("}\n\n", fn_start)
    body = html[fn_start:fn_end]
    assert "buildHistoryQuery(slaHistoryFilter)" in body


def test_clear_filter_buttons_reset_inputs_and_refetch():
    html = load_panel_html()
    fn_start = html.index("el('clearPauseHistoryBtn').addEventListener")
    fn_end = html.index("});", fn_start)
    body = html[fn_start:fn_end]
    assert "fetchAll()" in body
    assert "start: ''" in body
