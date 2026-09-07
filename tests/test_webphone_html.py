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
    "transferTarget", "transferBtn", "parkBtn", "consultBtn",
    "consultHeldPeer", "consultTargetPeer", "consultTargetState",
    "cancelConsultBtn", "completeConsultBtn",
    "callLog", "colleaguesPanel", "colleaguesList",
    "remoteAudio", "queueApiUrl", "queueList",
    "recordingsList", "refreshRecordingsBtn", "recordingsSearchInput", "recordingsSearchBtn",
    "presencePanel", "presenceStatusSelect", "presenceNoteInput", "setPresenceBtn",
    "pausePanel", "pauseReasonSelect", "pauseBtn", "unpauseBtn",
    "lineSwitcher", "linePill0", "linePill1",
    "secondLineBanner", "secondLinePeer", "answerSecondLineBtn", "declineSecondLineBtn",
    "missedCallsList", "metricsPanel", "metricsGrid",
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
    ANTES de cair na regra geral que rejeita uma terceira chamada.
    """
    html = load_html()
    handler_start = html.index("function handleNewSession")
    reject_rule_pos = html.index("duas linhas já estão ocupadas", handler_start)
    consult_check_pos = html.index("expectingConsultCall && session.direction", handler_start)
    assert consult_check_pos < reject_rule_pos, (
        "A checagem de chamada de consulta precisa vir antes da regra "
        "que rejeita a terceira chamada"
    )


def test_queue_pickup_sends_channel_to_correct_endpoint():
    html = load_html()
    pickup_start = html.index("function pickupFromQueue")
    pickup_end = html.index("}", html.index("catch", pickup_start))
    handler_body = html[pickup_start:pickup_end]
    assert "/api/queue/pickup" in handler_body
    assert "method: 'POST'" in handler_body
    assert "channel" in handler_body


def test_queue_polling_starts_on_registration_and_stops_on_disconnect():
    html = load_html()
    assert "startQueuePolling()" in html
    assert "stopQueuePolling()" in html


def test_recordings_panel_uses_embedded_audio_player():
    html = load_html()
    render_start = html.index("function renderRecordings")
    render_end = html.index("el('refreshRecordingsBtn')", render_start)
    handler_body = html[render_start:render_end]
    assert "<audio controls" in handler_body
    assert "/recordings/" in handler_body


def test_answering_second_line_holds_the_first():
    """
    O ponto central do multi-chamada: atender a linha 2 precisa
    colocar a linha 1 em espera antes - senão as duas ficam com áudio
    aberto ao mesmo tempo, o que não faz sentido numa chamada só.
    """
    html = load_html()
    fn_start = html.index("function answerLine")
    fn_end = html.index("function handleLineEnded")
    body = html[fn_start:fn_end]
    hold_pos = body.index("current.session.hold()")
    answer_pos = body.index("line.session.answer(")
    assert hold_pos < answer_pos, (
        "answerLine precisa colocar a linha atual em espera ANTES de "
        "atender a nova linha"
    )


def test_line_ended_falls_back_to_other_line_automatically():
    """
    Se a linha ativa cai (chamador desligou, etc.) e existe uma
    segunda linha em espera, a interface precisa voltar pra ela
    automaticamente (tirando da espera) em vez de deixar a telefonista
    "perdida" sem call ativa visível.
    """
    html = load_html()
    fn_start = html.index("function handleLineEnded")
    fn_end = html.index("function resetCallUI")
    body = html[fn_start:fn_end]
    assert "otherLine.session.unhold()" in body


def test_third_simultaneous_call_is_rejected():
    """
    O limite é 2 linhas - uma terceira chamada simultânea (ambas as
    linhas já ocupadas) precisa ser recusada automaticamente.
    """
    html = load_html()
    fn_start = html.index("function handleNewSession")
    fn_end = html.index("function wireSessionEvents")
    body = html[fn_start:fn_end]
    assert "freeIndex === -1" in body
    assert "session.terminate()" in body


def test_line_switcher_prevents_switching_to_unanswered_line():
    html = load_html()
    fn_start = html.index("function switchToLine")
    fn_end = html.index("el('linePill0')")
    body = html[fn_start:fn_end]
    assert "line.session.isEstablished()" in body


def test_missed_calls_polling_starts_and_stops_with_connection():
    html = load_html()
    assert "startMissedCallsPolling()" in html
    assert "stopMissedCallsPolling()" in html
    assert "/api/missed-calls" in html


def test_metrics_polling_starts_and_stops_with_connection():
    html = load_html()
    assert "startMetricsPolling()" in html
    assert "stopMetricsPolling()" in html
    assert "/api/metrics/today" in html


def test_screen_pop_link_built_from_configurable_template():
    """
    Screen-pop (backlog #13) é implementado como link clicável, não
    window.open() automático - abrir sem gesto do usuário é bloqueado
    por popup blocker na grande maioria dos navegadores.
    """
    html = load_html()
    fn_start = html.index("function setScreenPopLink")
    fn_end = html.index("function resetCallUI")
    body = html[fn_start:fn_end]
    assert "crmScreenPopUrl.replace('{numero}'" in body
    assert "window.open" not in html  # em nenhum lugar do arquivo


def test_incoming_call_views_set_screen_pop_link():
    html = load_html()
    fn_start = html.index("function handleNewSession")
    fn_end = html.index("function wireSessionEvents")
    body = html[fn_start:fn_end]
    assert "setScreenPopLink('screenPopLink', peer)" in body
    assert "setScreenPopLink('secondLineScreenPopLink', peer)" in body


def test_recordings_search_sends_caller_number_filter():
    html = load_html()
    fn_start = html.index("function fetchRecordings")
    fn_end = html.index("function renderRecordings")
    body = html[fn_start:fn_end]
    assert "caller_number=" in body
    assert "recordingsSearchInput" in body


def test_presence_update_sends_own_extension_status_and_note():
    html = load_html()
    fn_start = html.index("el('setPresenceBtn').addEventListener")
    fn_end = html.index("});", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "/api/presence/${myExtension}" in body
    assert "presenceStatusSelect" in body
    assert "presenceNoteInput" in body


def test_pickup_sends_own_extension_along_with_channel():
    """
    Com múltiplas telefonistas, o pickup precisa dizer ao queue-api
    QUEM está puxando a chamada (myExtension), não só qual chamada -
    senão o Asterisk não saberia pra qual ramal redirecionar.
    """
    html = load_html()
    fn_start = html.index("function pickupFromQueue")
    fn_end = html.index("}", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "extension: myExtension" in body


def test_my_extension_is_captured_on_registration():
    html = load_html()
    assert "myExtension = extension;" in html


def test_pwa_manifest_and_service_worker_are_linked():
    html = load_html()
    assert 'rel="manifest"' in html
    assert "serviceWorker.register(" in html


def test_incoming_call_triggers_ringtone_and_notification():
    """
    As duas chamadas recebidas possíveis (linha 1 direto, linha 2 via
    banner) precisam disparar campainha E notificação nativa - é isso
    que faz a telefonista perceber a chamada com a aba em segundo
    plano (o pedido original do backlog #9).
    """
    html = load_html()
    fn_start = html.index("function handleNewSession")
    fn_end = html.index("function wireSessionEvents")
    body = html[fn_start:fn_end]
    assert "startRingtone()" in body
    assert "notifyIncomingCall(peer)" in body


def test_ringtone_stops_on_answer_and_on_decline():
    html = load_html()
    answer_fn = html[html.index("function answerLine"):html.index("function handleLineEnded")]
    assert "stopRingtone()" in answer_fn

    decline_calls = html.count("stopRingtone(); session.terminate();")
    assert decline_calls == 2  # declineBtn e declineSecondLineBtn


def test_park_button_does_blind_transfer_to_parking_extension():
    """
    Backlog #41: estacionar é uma transferência cega pra vaga "75"
    (ver asterisk/res_parking.conf) - mesma técnica do transferBtn,
    reaproveitada, não um mecanismo novo.
    """
    html = load_html()
    fn_start = html.index("el('parkBtn').addEventListener")
    fn_end = html.index("});", fn_start)
    body = html[fn_start:fn_end]
    assert "session.refer(`sip:75@" in body


# ---------- Pausa da fila (backlog #44) ----------

def test_pause_button_sends_reason_and_toggles_unpause_button():
    html = load_html()
    fn_start = html.index("function sendPauseRequest")
    fn_end = html.index("el('pauseBtn').addEventListener")
    body = html[fn_start:fn_end]
    assert "/api/queue/pause" in body
    assert "extension: myExtension" in body
    assert "'unpauseBtn').style.display" in body


def test_unpause_sends_empty_reason():
    """Despausar não deve exigir nem enviar um motivo - só pausar precisa disso."""
    html = load_html()
    fn_start = html.index("el('unpauseBtn').addEventListener")
    fn_end = html.index("});", fn_start)
    body = html[fn_start:fn_end]
    assert "sendPauseRequest(false, '')" in body
