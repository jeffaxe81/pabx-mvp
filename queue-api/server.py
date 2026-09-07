"""
API HTTP mínima (biblioteca padrão do Python, sem Flask/FastAPI de
propósito - um serviço a mais rodando, um Dockerfile mais simples)
que expõe o estado da fila pro webphone.

Endpoints:
  GET  /api/queue                -> lista de chamadas esperando
  POST /api/queue/pickup         -> {"channel": "..."} puxa uma
                                     chamada específica pro ramal da
                                     telefonista (Redirect via AMI)

CORS liberado (Access-Control-Allow-Origin: *) porque o webphone é
servido por um container nginx diferente (porta 8082) do desta API.
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from ami_client import AMIClient
from queue_state import QueueStateTracker
from recordings import list_recordings, safe_recording_path
from recordings import delete_expired_recordings
from missed_calls import parse_missed_call_event, MissedCallsLog
from notifiers import dispatch_notifications
from click_to_call import build_originate_action, validate_click_to_call_request
from campaigns import (
    create_campaign, load_campaigns, find_campaign, next_pending_contact,
    mark_contact_calling, mark_contact_result, campaign_summary,
    extract_dialed_number,
)
from callbacks import (
    parse_callback_request_event, add_callback_request, load_callbacks,
    find_callback, next_pending_callback, mark_callback_calling, mark_callback_result,
)
from survey import parse_survey_event, SurveyStore, average_score, score_distribution, summarize_by_operator
from metrics import DailyMetrics
from pickup import validate_pickup_request
from extension_states import ExtensionStateTracker
from reports import parse_cdr_for_report, CallLogStore, aggregate, group_by, extract_operator
from screen_pop import dispatch_screen_pop
from fraud_detection import CallRateTracker, FraudAlertsLog, is_external_call, is_over_spending_limit
from quality_monitoring import parse_quality_event, is_poor_quality, QualityLog

AMI_HOST = os.environ.get("AMI_HOST", "127.0.0.1")
AMI_PORT = int(os.environ.get("AMI_PORT", "5038"))
AMI_USERNAME = os.environ.get("AMI_USERNAME", "queue-api")
AMI_SECRET = os.environ.get("AMI_SECRET", "troque_esta_senha_ami")
PICKUP_CONTEXT = os.environ.get("PICKUP_CONTEXT", "pickup-target")
PICKUP_ALLOWED_EXTENSIONS = [
    e.strip() for e in os.environ.get("PICKUP_ALLOWED_EXTENSIONS", "t1-recepcao,t1-recepcao-2").split(",") if e.strip()
]
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8090"))
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "/app/recordings")
# Retenção de gravações (backlog #15) - 0 (padrão) = desabilitado.
# Apagar gravação é irreversível, então isso é opt-in de propósito.
RECORDINGS_RETENTION_DAYS = int(os.environ.get("RECORDINGS_RETENTION_DAYS", "0"))
CALL_LOG_PATH = os.environ.get("CALL_LOG_PATH", "/app/data/call_log.jsonl")

# Screen-pop pro CRM (PABX -> CRM) - vazio = desabilitado, mesmo
# padrão de segurança/opt-in das outras integrações.
CRM_WEBHOOK_URL = os.environ.get("CRM_WEBHOOK_URL", "")

# Detecção de fraude (backlog #32) - tudo desligado/conservador por
# padrão: bloqueio automático é opt-in de propósito (bloquear um
# destino legítimo por engano é pior que deixar passar um alerta).
FRAUD_RATE_WINDOW_SECONDS = int(os.environ.get("FRAUD_RATE_WINDOW_SECONDS", "60"))
FRAUD_RATE_THRESHOLD = int(os.environ.get("FRAUD_RATE_THRESHOLD", "10"))
FRAUD_AUTO_BLOCK = os.environ.get("FRAUD_AUTO_BLOCK", "false").lower() == "true"
FRAUD_COST_PER_MINUTE = float(os.environ.get("FRAUD_COST_PER_MINUTE", "0"))
FRAUD_DAILY_COST_LIMIT = float(os.environ.get("FRAUD_DAILY_COST_LIMIT", "0"))  # 0 = desabilitado

# Monitoramento de qualidade (backlog #34) - só visibilidade, sem
# nenhuma ação com efeito colateral, então os limiares já vêm ativos
# por padrão (valores usados como referência comum de telefonia VoIP).
QUALITY_JITTER_THRESHOLD_MS = float(os.environ.get("QUALITY_JITTER_THRESHOLD_MS", "30"))
QUALITY_PACKET_LOSS_THRESHOLD_PERCENT = float(os.environ.get("QUALITY_PACKET_LOSS_THRESHOLD_PERCENT", "3"))

# Notificação de chamada perdida - canais habilitados via variável de
# ambiente (ex: "email,whatsapp"). Vazio = notificação desabilitada,
# mas o histórico de chamadas perdidas continua funcionando.
NOTIFY_CHANNELS = [c.strip() for c in os.environ.get("NOTIFY_CHANNELS", "").split(",") if c.strip()]
NOTIFY_CONFIG = {
    "channels": NOTIFY_CHANNELS,
    "smtp": {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": os.environ.get("SMTP_PORT", "587"),
        "username": os.environ.get("SMTP_USERNAME", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_addr": os.environ.get("SMTP_FROM", ""),
        "to_addr": os.environ.get("SMTP_TO", ""),
        "use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() == "true",
    },
    "whatsapp": {
        "phone_number_id": os.environ.get("WHATSAPP_PHONE_NUMBER_ID", ""),
        "access_token": os.environ.get("WHATSAPP_ACCESS_TOKEN", ""),
        "to_number": os.environ.get("WHATSAPP_TO_NUMBER", ""),
    },
}

# Click-to-call (CRM externo disparando ligação) - desligado por
# padrão (api_key vazia) até ser configurado explicitamente.
CLICK_TO_CALL_CONTEXT = os.environ.get("CLICK_TO_CALL_CONTEXT", "click-to-call")
CLICK_TO_CALL_CONFIG = {
    "api_key": os.environ.get("CLICK_TO_CALL_API_KEY", ""),
    "allowed_extensions": [
        e.strip() for e in os.environ.get("CLICK_TO_CALL_ALLOWED_EXTENSIONS", "t1-recepcao").split(",") if e.strip()
    ],
}

# Discador automático / campanhas (backlog #25) - reaproveita a MESMA
# chave do click-to-call (mesma categoria de risco: originar chamada
# via AMI) e o mesmo contexto de dialplan.
CAMPAIGNS_PATH = os.environ.get("CAMPAIGNS_PATH", "/app/data/campaigns.json")

# Chamada de retorno / callback (backlog #26) - mesma chave e contexto
# de risco do click-to-call/campanhas (originar chamada via AMI).
CALLBACKS_PATH = os.environ.get("CALLBACKS_PATH", "/app/data/callbacks.json")
CALLBACK_CONNECT_CONTEXT = os.environ.get("CALLBACK_CONNECT_CONTEXT", "callback-connect")
SURVEY_PATH = os.environ.get("SURVEY_PATH", "/app/data/survey.jsonl")

state = QueueStateTracker()
missed_calls_log = MissedCallsLog()
daily_metrics = DailyMetrics()
extension_states = ExtensionStateTracker()
call_log_store = CallLogStore(CALL_LOG_PATH)
rate_tracker = CallRateTracker()
fraud_alerts_log = FraudAlertsLog()
quality_log = QualityLog()
ami = None  # inicializado em main(), None durante os testes automatizados


def handle_ami_event(event: dict):
    """Callback único do AMI: alimenta fila, chamadas perdidas, métricas, estado dos ramais, relatórios, fraude e qualidade."""
    state.apply_event(event)
    daily_metrics.apply_cdr_event(event)
    extension_states.apply_event(event)

    quality = parse_quality_event(event)
    if quality:
        poor = is_poor_quality(quality, QUALITY_JITTER_THRESHOLD_MS, QUALITY_PACKET_LOSS_THRESHOLD_PERCENT)
        quality_log.append(quality, poor)

    report_record = parse_cdr_for_report(event)
    if report_record:
        call_log_store.append(report_record)

        # Limite de gasto diário (checado após cada chamada atendida
        # terminar - não bloqueia em tempo real no meio da ligação,
        # ver limitação no manual 27)
        if report_record.get("operator") and FRAUD_DAILY_COST_LIMIT > 0:
            today = report_record["date"]
            todays_calls = call_log_store.query(start=today, end=today, operator=report_record["operator"])
            if is_over_spending_limit(todays_calls, FRAUD_COST_PER_MINUTE, FRAUD_DAILY_COST_LIMIT):
                fraud_alerts_log.append(
                    "limite_gasto", report_record["operator"],
                    f"Limite diário de R$ {FRAUD_DAILY_COST_LIMIT:.2f} excedido",
                )

    check_call_volume(event)

    screen_pop_error = dispatch_screen_pop(event, CRM_WEBHOOK_URL)
    if screen_pop_error:
        print(f"[AVISO] falha no screen-pop: {screen_pop_error}")

    apply_campaign_dial_result(event)
    apply_callback_dial_result(event)

    callback_request = parse_callback_request_event(event)
    if callback_request:
        add_callback_request(CALLBACKS_PATH, callback_request["caller_id_num"], callback_request["caller_id_name"])

    survey_result = parse_survey_event(event)
    if survey_result:
        SurveyStore(SURVEY_PATH).append(survey_result)


def apply_callback_dial_result(event: dict):
    """Mesmo mecanismo de correlação de campanhas, aplicado aos callbacks 'discando'."""
    if event.get("Event") != "DialEnd":
        return

    disposition = event.get("DialStatus")
    number = extract_dialed_number(event)
    if not disposition or not number:
        return

    for callback in load_callbacks(CALLBACKS_PATH):
        if callback["caller_id_num"] == number and callback["status"] == "discando":
            mark_callback_result(CALLBACKS_PATH, callback["id"], disposition)
            break


def apply_campaign_dial_result(event: dict):
    """
    Quando um DialEnd chega, confere se o número discado corresponde a
    um contato de campanha "discando" no momento - se sim, registra o
    resultado (atendida/ocupado/sem resposta/etc.).
    """
    if event.get("Event") != "DialEnd":
        return

    disposition = event.get("DialStatus")
    number = extract_dialed_number(event)
    if not disposition or not number:
        return

    for campaign in load_campaigns(CAMPAIGNS_PATH):
        contact = next(
            (c for c in campaign["contacts"] if c["number"] == number and c["status"] == "discando"),
            None,
        )
        if contact:
            mark_contact_result(CAMPAIGNS_PATH, campaign["id"], number, disposition)
            break


def check_call_volume(event: dict):
    """
    Volume anormal de chamadas de saída pelo mesmo ramal - o padrão
    clássico de um PABX comprometido discando em massa.
    """
    if not is_external_call(event) or event.get("Event") != "DialBegin":
        return

    source_extension = extract_operator(event.get("Channel", ""))
    destination = event.get("DestExten", "")
    if not source_extension:
        return

    rate_tracker.track_call(source_extension, destination)
    if rate_tracker.is_abnormal(source_extension, FRAUD_RATE_WINDOW_SECONDS, FRAUD_RATE_THRESHOLD):
        fraud_alerts_log.append(
            "volume_anormal", source_extension,
            f"Mais de {FRAUD_RATE_THRESHOLD} chamadas externas em {FRAUD_RATE_WINDOW_SECONDS}s",
        )
        if FRAUD_AUTO_BLOCK and destination and ami is not None:
            try:
                ami.block_number(destination)
                fraud_alerts_log.append("bloqueio_automatico", source_extension, f"Número {destination} bloqueado automaticamente")
            except Exception as exc:  # noqa: BLE001
                print(f"[AVISO] falha ao bloquear automaticamente {destination}: {exc}")

    missed = parse_missed_call_event(event)
    if missed:
        missed_calls_log.append(missed)
        errors = dispatch_notifications(missed, NOTIFY_CONFIG)
        for error in errors:
            print(f"[AVISO] falha ao notificar chamada perdida: {error}")


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(204, {})

    def do_GET(self):
        if self.path.startswith("/api/queue"):
            self._send_json(200, {"waiting": state.waiting_list()})
        elif self.path.startswith("/api/recordings"):
            self._handle_list_recordings()
        elif self.path.startswith("/api/missed-calls"):
            self._send_json(200, {"missed_calls": missed_calls_log.list()})
        elif self.path.startswith("/api/fraud-alerts"):
            self._send_json(200, {"alerts": fraud_alerts_log.list()})
        elif self.path.startswith("/api/quality"):
            self._handle_quality_query()
        elif self.path.startswith("/api/metrics/today"):
            self._send_json(200, daily_metrics.snapshot())
        elif self.path.startswith("/api/extension-states"):
            self._send_json(200, {"extensions": extension_states.snapshot()})
        elif self.path.startswith("/api/reports"):
            self._handle_reports()
        elif self.path.startswith("/api/campaigns/"):
            self._handle_get_campaign()
        elif self.path.startswith("/api/campaigns"):
            self._handle_list_campaigns()
        elif self.path.startswith("/api/callbacks"):
            self._handle_list_callbacks()
        elif self.path.startswith("/api/satisfaction"):
            self._handle_satisfaction_query()
        elif self.path.startswith("/recordings/"):
            self._serve_recording_file()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_quality_query(self):
        query = parse_qs(urlparse(self.path).query)
        only_poor = query.get("only_poor", ["false"])[0].lower() == "true"
        self._send_json(200, {"quality_reports": quality_log.list(only_poor=only_poor)})

    def _handle_satisfaction_query(self):
        query = parse_qs(urlparse(self.path).query)
        operator = query.get("operator", [None])[0]
        records = SurveyStore(SURVEY_PATH).query(operator=operator)

        if query.get("group_by", [None])[0] == "operator":
            self._send_json(200, {"by_operator": summarize_by_operator(records)})
        else:
            self._send_json(200, {
                "average": average_score(records),
                "count": len(records),
                "distribution": score_distribution(records),
            })    def _handle_reports(self):
        query = parse_qs(urlparse(self.path).query)
        start = query.get("start", [None])[0]
        end = query.get("end", [None])[0]
        operator = query.get("operator", [None])[0]
        tenant = query.get("tenant", [None])[0]
        group_field = query.get("group_by", [None])[0]

        records = call_log_store.query(start=start, end=end, operator=operator, tenant=tenant)

        if group_field in ("operator", "tenant", "date"):
            self._send_json(200, {"groups": group_by(records, group_field)})
        else:
            self._send_json(200, aggregate(records))

    def _handle_list_recordings(self):
        query = parse_qs(urlparse(self.path).query)
        recordings = list_recordings(
            RECORDINGS_DIR,
            caller_number=query.get("caller_number", [None])[0],
            destination=query.get("destination", [None])[0],
            start_date=query.get("start_date", [None])[0],
            end_date=query.get("end_date", [None])[0],
        )
        self._send_json(200, {"recordings": recordings})

    def _serve_recording_file(self):
        filename = self.path[len("/recordings/"):]
        resolved = safe_recording_path(RECORDINGS_DIR, filename)
        if resolved is None:
            self._send_json(404, {"error": "gravacao nao encontrada"})
            return

        content_type = "audio/wav" if resolved.suffix.lower() == ".wav" else "application/octet-stream"
        data = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path == "/api/queue/pickup":
            self._handle_pickup()
        elif self.path == "/api/click-to-call":
            self._handle_click_to_call()
        elif self.path == "/api/campaigns":
            self._handle_create_campaign()
        elif self.path.startswith("/api/campaigns/") and self.path.endswith("/dial-next"):
            self._handle_dial_next_contact()
        elif self.path == "/api/callbacks/dial-next":
            self._handle_dial_next_callback()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_pickup(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "JSON invalido"})
            return

        ok, error, channel, extension = validate_pickup_request(
            data, {"allowed_extensions": PICKUP_ALLOWED_EXTENSIONS}
        )
        if not ok:
            status = 403 if "autorizado" in error else 400
            self._send_json(status, {"error": error})
            return

        if ami is None:
            self._send_json(503, {"error": "AMI nao conectado"})
            return

        response = ami.redirect_channel(channel, PICKUP_CONTEXT, exten=extension)
        if response.get("Response") == "Success":
            state.remove(channel)
            self._send_json(200, {"ok": True})
        else:
            self._send_json(502, {"error": "falha no redirect", "detail": response})

    def _handle_click_to_call(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "JSON invalido"})
            return

        api_key = self.headers.get("X-Click-To-Call-Key", "")
        ok, error, extension, number = validate_click_to_call_request(data, api_key, CLICK_TO_CALL_CONFIG)

        if not ok:
            status = 403 if ("chave" in error or "autorizado" in error or "configurado" in error) else 400
            self._send_json(status, {"error": error})
            return

        if ami is None:
            self._send_json(503, {"error": "AMI nao conectado"})
            return

        action = build_originate_action(f"PJSIP/{extension}", number, CLICK_TO_CALL_CONTEXT)
        response = ami.send_action(action)
        if response.get("Response") == "Success":
            self._send_json(200, {"ok": True})
        else:
            self._send_json(502, {"error": "falha ao originar chamada", "detail": response})

    def _require_campaign_api_key(self):
        """
        Campanhas usam a MESMA chave e checagem do click-to-call
        (mesma categoria de risco: originar chamada via AMI). Retorna
        True se autorizado, senão já respondeu o erro e retorna False.
        """
        api_key = self.headers.get("X-Click-To-Call-Key", "")
        configured_key = CLICK_TO_CALL_CONFIG.get("api_key", "")
        if not configured_key:
            self._send_json(503, {"error": "campanhas não configuradas (sem API key definida)"})
            return False
        if api_key != configured_key:
            self._send_json(403, {"error": "chave de API inválida"})
            return False
        return True

    def _handle_list_campaigns(self):
        if not self._require_campaign_api_key():
            return
        campaigns = load_campaigns(CAMPAIGNS_PATH)
        summaries = [{**c, "summary": campaign_summary(c)} for c in campaigns]
        self._send_json(200, {"campaigns": summaries})

    def _handle_get_campaign(self):
        if not self._require_campaign_api_key():
            return
        campaign_id = self.path[len("/api/campaigns/"):].split("/")[0]
        campaign = find_campaign(load_campaigns(CAMPAIGNS_PATH), campaign_id)
        if not campaign:
            self._send_json(404, {"error": "campanha não encontrada"})
            return
        self._send_json(200, {**campaign, "summary": campaign_summary(campaign)})

    def _handle_create_campaign(self):
        if not self._require_campaign_api_key():
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "JSON invalido"})
            return

        ok, error, campaign = create_campaign(CAMPAIGNS_PATH, data)
        if not ok:
            self._send_json(400, {"error": error})
            return
        self._send_json(201, campaign)

    def _handle_dial_next_contact(self):
        if not self._require_campaign_api_key():
            return

        campaign_id = self.path[len("/api/campaigns/"):].split("/")[0]
        campaign = find_campaign(load_campaigns(CAMPAIGNS_PATH), campaign_id)
        if not campaign:
            self._send_json(404, {"error": "campanha não encontrada"})
            return

        contact = next_pending_contact(campaign)
        if not contact:
            self._send_json(200, {"done": True, "message": "nenhum contato pendente"})
            return

        if ami is None:
            self._send_json(503, {"error": "AMI nao conectado"})
            return

        mark_contact_calling(CAMPAIGNS_PATH, campaign_id, contact["number"])
        action = build_originate_action(f"PJSIP/{campaign['agent_extension']}", contact["number"], CLICK_TO_CALL_CONTEXT)
        response = ami.send_action(action)
        if response.get("Response") == "Success":
            self._send_json(200, {"ok": True, "dialing": contact["number"]})
        else:
            self._send_json(502, {"error": "falha ao originar chamada", "detail": response})

    def _handle_list_callbacks(self):
        if not self._require_campaign_api_key():
            return
        self._send_json(200, {"callbacks": load_callbacks(CALLBACKS_PATH)})

    def _handle_dial_next_callback(self):
        """
        Diferente de campanhas: aqui o Originate disca DIRETO pro
        número do cliente através do tronco (não pra um ramal interno
        primeiro) - quando ele atender, o contexto callback-connect
        conecta com o atendente. É o mesmo mecanismo do click-to-call,
        só que na ordem inversa.
        """
        if not self._require_campaign_api_key():
            return

        callback = next_pending_callback(load_callbacks(CALLBACKS_PATH))
        if not callback:
            self._send_json(200, {"done": True, "message": "nenhum callback pendente"})
            return

        if ami is None:
            self._send_json(503, {"error": "AMI nao conectado"})
            return

        mark_callback_calling(CALLBACKS_PATH, callback["id"])
        action = {
            "Action": "Originate",
            "Channel": f"PJSIP/{callback['caller_id_num']}@gateway-tdm",
            "Context": CALLBACK_CONNECT_CONTEXT,
            "Exten": "s",
            "Priority": "1",
            "Async": "true",
            "Timeout": "30000",
            "CallerID": f'"Retorno de chamada" <{callback["caller_id_num"]}>',
        }
        response = ami.send_action(action)
        if response.get("Response") == "Success":
            self._send_json(200, {"ok": True, "dialing": callback["caller_id_num"]})
        else:
            self._send_json(502, {"error": "falha ao originar chamada", "detail": response})

    def log_message(self, format, *args):
        pass  # log padrão do BaseHTTPRequestHandler é barulhento demais


def _retention_cleanup_loop():
    """
    Roda em background, uma vez por dia, apagando gravações mais
    antigas que RECORDINGS_RETENTION_DAYS - só faz alguma coisa se
    essa variável for > 0 (desabilitado por padrão).
    """
    while True:
        if RECORDINGS_RETENTION_DAYS > 0:
            deleted = delete_expired_recordings(RECORDINGS_DIR, RECORDINGS_RETENTION_DAYS)
            if deleted:
                print(f"[retenção] {len(deleted)} gravação(ões) expurgada(s): {deleted}")
        time.sleep(24 * 3600)


def main():
    global ami
    ami = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET, on_event=handle_ami_event)
    ami.connect_and_login()
    ami.start_event_loop()

    if RECORDINGS_RETENTION_DAYS > 0:
        threading.Thread(target=_retention_cleanup_loop, daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"queue-api ouvindo em :{HTTP_PORT}, conectado ao AMI em {AMI_HOST}:{AMI_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
