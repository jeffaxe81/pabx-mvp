"""
API HTTP mínima (biblioteca padrão do Python, sem Flask/FastAPI de
propósito - um serviço a mais rodando, um Dockerfile mais simples)
que expõe o estado da fila pro webphone.

Endpoints:
  GET  /api/queue                -> lista de chamadas esperando
  POST /api/queue/pickup         -> {"channel": "..."} puxa uma
                                     chamada específica pro ramal da
                                     telefonista (Redirect via AMI)

Rotas legadas seguem com CORS amplo, mas /api/queue e /api/queue/pickup
exigem Bearer com tenant e Origin explicitamente permitido. Nunca colocar
tokens de fila em URLs ou em código estático publicado pelo Nginx.
"""
import json
import re
import secrets
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

from ami_client import AMIClient
from queue_state import QueueStateTracker
from recordings import list_recordings, open_recording_file
from recordings import delete_expired_recordings
from recording_access import (
    load_recording_policy, authenticate_recordings, can_read_recording, allowed_browser_origin,
)
from missed_calls import parse_missed_call_event, MissedCallsLog
from notifiers import dispatch_notifications
from outbound_admission import OriginateAdmission
from click_to_call import build_originate_action, validate_click_to_call_request
from campaigns import (
    create_campaign, load_campaigns, find_campaign, next_pending_contact,
    mark_contact_calling, mark_contact_result, campaign_summary,
    extract_dialed_number, DISPOSITION_TO_STATUS as CAMPAIGN_DISPOSITIONS,
)
from callbacks import (
    parse_callback_request_event, add_callback_request, load_callbacks,
    find_callback, next_pending_callback, mark_callback_calling, mark_callback_result,
    cancel_pending_callback, summarize_callbacks,
    DISPOSITION_TO_STATUS as CALLBACK_DISPOSITIONS,
)
from survey import parse_survey_event, SurveyStore, average_score, score_distribution, summarize_by_operator
from presence import validate_presence_input, load_presence, set_presence, clear_presence, merge_presence_into_states
from agent_pause import validate_pause_request, AgentPauseStore, merge_pause_into_states, PauseHistoryStore, summarize_pause_time_by_reason, summarize_pause_time_by_extension, filter_pause_records_by_date_range
from metrics import DailyMetrics, TenantDailyMetrics
from queue_sla import QueueSLATracker, SLAHistoryStore, summarize_sla_history_by_date, filter_sla_history_by_date_range
from pickup import validate_pickup_request, pickup_matches_queue, queue_tenant
from queue_access import load_queue_policy, authenticate_queue, may_pickup
from extension_states import ExtensionStateTracker
from reports import parse_cdr_for_report, CallLogStore, aggregate, group_by, extract_operator
from screen_pop import dispatch_screen_pop
from fraud_detection import CallRateTracker, FraudAlertsLog, is_external_call, is_over_spending_limit
from quality_monitoring import parse_quality_event, is_poor_quality, QualityLog
from monitoring_access import extension_tenant, channel_tenant
from monitoring_access import monitoring_event_tenant, scoped_monitoring_entries
from supervision_summary import build_supervision_summary
from supervision_diagnostics import evaluate_supervision_diagnostics
from outbound_safety import outbound_lock, atomic_write_json
from outbound_correlation import matches_dial_event, matches_originate_response

AMI_HOST = os.environ.get("AMI_HOST", "127.0.0.1")
AMI_PORT = int(os.environ.get("AMI_PORT", "5038"))
AMI_USERNAME = os.environ.get("AMI_USERNAME", "queue-api")
AMI_SECRET = os.environ.get("AMI_SECRET", "troque_esta_senha_ami")
PICKUP_CONTEXT = os.environ.get("PICKUP_CONTEXT", "pickup-target")
PICKUP_ALLOWED_EXTENSIONS = [
    e.strip() for e in os.environ.get("PICKUP_ALLOWED_EXTENSIONS", "t1-recepcao,t1-recepcao-2,t2-recepcao,t2-recepcao-2").split(",") if e.strip()
]
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8090"))
SLA_THRESHOLD_SECONDS = int(os.environ.get("SLA_THRESHOLD_SECONDS", "20"))
SLA_HISTORY_PATH = os.environ.get("SLA_HISTORY_PATH", "/app/data/sla_history.jsonl")
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "/app/recordings")
RECORDINGS_ACCESS_POLICY_PATH = os.environ.get("RECORDINGS_ACCESS_POLICY_PATH", "/app/data/recording_access.json")
RECORDINGS_CORS_ORIGINS = set(filter(None, (v.strip() for v in os.environ.get("RECORDINGS_CORS_ORIGINS", "").split(","))))
QUEUE_ACCESS_POLICY_PATH = os.environ.get("QUEUE_ACCESS_POLICY_PATH", "/app/data/queue_access.json")
QUEUE_CORS_ORIGINS = set(filter(None, (v.strip() for v in os.environ.get("QUEUE_CORS_ORIGINS", "").split(","))))
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
# Destinatários SMTP/WhatsApp legados são globais. Só um tenant
# explicitamente cadastrado pode usar estes destinatários.
# Sem NOTIFY_TENANT, notificações externas ficam negadas.
NOTIFY_TENANT = os.environ.get("NOTIFY_TENANT", "").strip()
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
        e.strip() for e in os.environ.get("CLICK_TO_CALL_ALLOWED_EXTENSIONS", "t1-recepcao,t2-recepcao").split(",") if e.strip()
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
PRESENCE_PATH = os.environ.get("PRESENCE_PATH", "/app/data/presence.json")
PAUSE_HISTORY_PATH = os.environ.get("PAUSE_HISTORY_PATH", "/app/data/pause_history.jsonl")

state = QueueStateTracker()
missed_calls_log = MissedCallsLog()
daily_metrics = DailyMetrics()
tenant_daily_metrics = TenantDailyMetrics()
sla_history_store = SLAHistoryStore(SLA_HISTORY_PATH)
queue_sla_tracker = QueueSLATracker(threshold_seconds=SLA_THRESHOLD_SECONDS, history_store=sla_history_store)
extension_states = ExtensionStateTracker()
pause_history_store = PauseHistoryStore(PAUSE_HISTORY_PATH)
agent_pause_store = AgentPauseStore(history_store=pause_history_store)
call_log_store = CallLogStore(CALL_LOG_PATH)
rate_tracker = CallRateTracker()
fraud_alerts_log = FraudAlertsLog()
quality_log = QualityLog()
ami = None  # inicializado em main(), None durante os testes automatizados
# Serializa seleção + claim persistido + Originate entre threads HTTP.
# Para múltiplos processos/instâncias ainda serão necessários locks distribuídos.
OUTBOUND_LOCK = threading.RLock()
# Limites por processo; para clusters é obrigatório usar controle distribuído.
CTI_ADMISSION = OriginateAdmission()


def handle_ami_event(event: dict):
    """Callback único do AMI: alimenta fila, chamadas perdidas, métricas, estado dos ramais, relatórios, fraude e qualidade."""
    state.apply_event(event)
    daily_metrics.apply_cdr_event(event)
    tenant_daily_metrics.apply_cdr_event(event)
    queue_sla_tracker.apply_event(event)
    extension_states.apply_event(event)
    agent_pause_store.apply_event(event)

    tenant = monitoring_event_tenant(event)
    quality = parse_quality_event(event)
    if quality and tenant:
        poor = is_poor_quality(quality, QUALITY_JITTER_THRESHOLD_MS, QUALITY_PACKET_LOSS_THRESHOLD_PERCENT)
        quality_log.append({**quality, "tenant": tenant}, poor)

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

    # Eventos AMI sem tenant demonstrável não entram em histórico nem
    # disparam notificação para outra empresa.
    missed = parse_missed_call_event(event)
    if missed and tenant:
        missed["tenant"] = tenant
        missed_calls_log.append(missed)
        if tenant == NOTIFY_TENANT:
            for error in dispatch_notifications(missed, NOTIFY_CONFIG):
                print(f"[AVISO] falha ao notificar chamada perdida: {error}")

    screen_pop_error = dispatch_screen_pop(event, CRM_WEBHOOK_URL)
    if screen_pop_error:
        print(f"[AVISO] falha no screen-pop: {screen_pop_error}")

    try:
        apply_originate_response(event)
        apply_campaign_dial_result(event)
        apply_callback_dial_result(event)
    except (OSError, UnicodeError, ValueError):
        # Corrupção do catálogo não pode interromper a recepção AMI.
        # Nenhum resultado ambíguo é atribuído a uma chamada.
        print("[AVISO] catalogo de outbound indisponivel; resultado AMI nao aplicado")

    callback_request = parse_callback_request_event(event)
    if callback_request:
        tenant = event.get("Tenant")
        if (isinstance(tenant, str)
                and extension_tenant(tenant + "-recepcao") == tenant
                and all(event.get(key) == tenant for key in ("AccountCode", "Accountcode")
                        if key in event)):
            try:
                with outbound_lock(CALLBACKS_PATH):
                    add_callback_request(CALLBACKS_PATH, callback_request["caller_id_num"],
                                         callback_request["caller_id_name"], tenant=tenant)
            except (OSError, UnicodeError, ValueError):
                # Preservar snapshot suspeito; não regravar como lista vazia.
                print("[AVISO] catalogo de callbacks indisponivel; pedido AMI nao persistido")

    survey_result = parse_survey_event(event)
    if survey_result and survey_result.get("tenant"):
        SurveyStore(SURVEY_PATH).append(survey_result)


def outbound_event_tenant(event):
    """Atribuição do resultado pelo AccountCode AMI ou ramal originador.

    Não inferir pela lista de contatos nem pelo número do cliente.
    Se informações se contradizem, nenhuma campanha é modificada.
    """
    account = event.get("AccountCode", event.get("Accountcode"))
    source = channel_tenant(event.get("Channel"))
    if account is not None:
        if not isinstance(account, str) or extension_tenant(account + "-recepcao") != account:
            return None
        other = event.get("Accountcode")
        if other is not None and other != account:
            return None
        if source is not None and source != account:
            return None
        return account
    return source


def apply_originate_response(event: dict):
    """Persist only an AMI OriginateResponse with exact ActionID + Uniqueid.

    An AMI response is an acknowledgement, never proof of call completion.
    Failures remain in 'discando' for a human to review; no auto-redial.
    """
    if event.get("Event") != "OriginateResponse":
        return
    with outbound_lock(CALLBACKS_PATH), outbound_lock(CAMPAIGNS_PATH):
        callbacks = load_callbacks(CALLBACKS_PATH)
        campaigns = load_campaigns(CAMPAIGNS_PATH)
        found = [(CALLBACKS_PATH, callback) for callback in callbacks
                 if callback.get("status") == "discando"
                 and matches_originate_response(event, callback)]
        found.extend((CAMPAIGNS_PATH, contact)
                     for campaign in campaigns for contact in campaign.get("contacts", [])
                     if contact.get("status") == "discando"
                     and matches_originate_response(
                         event, {**contact, "tenant": campaign.get("tenant")}))
        if len(found) != 1:
            return
        path, target = found[0]
        if target.get("originate_response") is not None:
            return  # late, duplicated, or contradictory event
        target["originate_response"] = event["Response"]
        target["originate_response_at"] = time.time()
        atomic_write_json(path, callbacks if path == CALLBACKS_PATH else campaigns)


def apply_callback_dial_result(event: dict):
    """Retorno de callback só é atualizado com tenant confiável no AMI."""
    if event.get("Event") != "DialEnd":
        return
    tenant = outbound_event_tenant(event)
    disposition = event.get("DialStatus")
    number = extract_dialed_number(event)
    if not tenant or not isinstance(disposition, str) or disposition not in CALLBACK_DISPOSITIONS or not number:
        return

    # Always acquire shared locks in the same order, even when AMI
    # events arrive during an Originate request in another process.
    with outbound_lock(CALLBACKS_PATH), outbound_lock(CAMPAIGNS_PATH):
        matches = [c for c in load_callbacks(CALLBACKS_PATH)
                   if c.get("tenant") == tenant and c.get("caller_id_num") == number
                   and c.get("status") == "discando" and matches_dial_event(event, c)
                   and c.get("originate_response") != "Failure"]
        other = [item for campaign in load_campaigns(CAMPAIGNS_PATH)
                 if campaign.get("tenant") == tenant
                 for item in campaign.get("contacts", [])
                 if item.get("number") == number and item.get("status") == "discando"]
        if any(matches_dial_event(event, item) for item in other):
            return  # conflicting claim across categories
        if len(matches) == 1:
            mark_callback_result(CALLBACKS_PATH, matches[0]["id"], disposition)


def apply_campaign_dial_result(event: dict):
    """Campanha e evento DialEnd precisam pertencer ao mesmo tenant."""
    if event.get("Event") != "DialEnd":
        return
    tenant = outbound_event_tenant(event)
    disposition = event.get("DialStatus")
    number = extract_dialed_number(event)
    if not tenant or not isinstance(disposition, str) or disposition not in CAMPAIGN_DISPOSITIONS or not number:
        return

    with outbound_lock(CALLBACKS_PATH), outbound_lock(CAMPAIGNS_PATH):
        matches = [(campaign, contact)
                   for campaign in load_campaigns(CAMPAIGNS_PATH)
                   if campaign.get("tenant") == tenant
                   for contact in campaign.get("contacts", [])
                   if contact.get("number") == number
                   and contact.get("status") == "discando"
                   and matches_dial_event(event, contact)
                   and contact.get("originate_response") != "Failure"]
        other = [c for c in load_callbacks(CALLBACKS_PATH)
                 if c.get("tenant") == tenant and c.get("caller_id_num") == number
                 and c.get("status") == "discando"]
        if any(matches_dial_event(event, item) for item in other):
            return  # conflicting claim across categories
        if len(matches) == 1:
            campaign, contact = matches[0]
            mark_contact_result(CAMPAIGNS_PATH, campaign["id"], contact["number"], disposition)


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

class Handler(BaseHTTPRequestHandler):
    # Rotas de gravações têm política e CORS separados das APIs antigas.
    # Elas jamais herdam o Access-Control-Allow-Origin: * de _send_json.
    def _is_queue_route(self):
        path = urlparse(self.path).path
        return (
            path in {
                "/api/queue", "/api/queue/pickup", "/api/queue/pause",
                "/api/supervision/summary",
                "/api/presence", "/api/reports/pauses", "/api/reports",
                "/api/metrics/today", "/api/metrics/sla", "/api/metrics/sla/history",
                "/api/missed-calls", "/api/fraud-alerts", "/api/quality",
                "/api/campaigns", "/api/callbacks", "/api/callbacks/dial-next",
                "/api/satisfaction", "/api/click-to-call",
            }
            or path.startswith("/api/presence/")
            or path.startswith("/api/campaigns/")
            or re.fullmatch(r"/api/callbacks/[0-9a-f]{12}/cancel", path) is not None
            or path == "/api/extension" + "-states"
        )

    def _queue_headers(self):
        origin = self.headers.get("Origin", "")
        if origin and allowed_browser_origin(origin, QUEUE_CORS_ORIGINS):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")

    def _send_queue_json(self, status, payload):
        body = b"" if status == 204 else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if status == 401:
            self.send_header("WWW-Authenticate", "Bearer")
        self._queue_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _require_queue_identity(self):
        origin = self.headers.get("Origin")
        if origin is not None and not allowed_browser_origin(origin, QUEUE_CORS_ORIGINS):
            self._send_queue_json(403, {"error": "origem nao permitida"})
            return None
        policy = load_queue_policy(QUEUE_ACCESS_POLICY_PATH)
        identity = authenticate_queue(self.headers.get("Authorization"), policy)
        if identity is None:
            self._send_queue_json(401, {"error": "credencial da fila invalida ou nao configurada"})
            return None
        return identity

    def _is_recording_route(self):
        path = urlparse(self.path).path
        return path == "/api/recordings" or path.startswith("/recordings/")

    def _recordings_headers(self):
        origin = self.headers.get("Origin", "")
        if origin and allowed_browser_origin(origin, RECORDINGS_CORS_ORIGINS):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")

    def _send_recordings_json(self, status, payload):
        body = b"" if status == 204 else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if status == 401:
            self.send_header("WWW-Authenticate", "Bearer")
        self._recordings_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _require_recording_identity(self):
        origin = self.headers.get("Origin")
        if origin is not None and not allowed_browser_origin(origin, RECORDINGS_CORS_ORIGINS):
            self._send_recordings_json(403, {"error": "origem não permitida"})
            return None
        policy = load_recording_policy(RECORDINGS_ACCESS_POLICY_PATH)
        identity = authenticate_recordings(self.headers.get("Authorization"), policy)
        if not identity:
            self._send_recordings_json(401, {"error": "credencial de gravação inválida ou não configurada"})
            return None
        return policy, identity

    def _send_json(self, status: int, payload: dict):
        """Resposta mínima para rotas desconhecidas, sem CORS permissivo.

        APIs reconhecidas usam _send_queue_json / _send_recordings_json,
        que aplicam autenticação e CORS por origem. Não publicar wildcard
        na rota de fallback: uma API adicionada sem classificação explícita
        não deve herdar permissões de acesso pelo navegador.
        """
        body = b"" if status == 204 else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self):
        if self._is_queue_route():
            origin = self.headers.get("Origin")
            if not allowed_browser_origin(origin, QUEUE_CORS_ORIGINS):
                self._send_queue_json(403, {"error": "origem nao permitida"})
                return
            self.send_response(204)
            self._queue_headers()
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            allowed_headers = "Authorization, Content-Type"
            if urlparse(self.path).path.startswith(("/api/campaigns", "/api/callbacks")) or urlparse(self.path).path == "/api/click-to-call":
                allowed_headers += ", X-Click-To-Call-Key, X-Idempotency-Key"
            self.send_header("Access-Control-Allow-Headers", allowed_headers)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self._is_recording_route():
            origin = self.headers.get("Origin")
            if not allowed_browser_origin(origin, RECORDINGS_CORS_ORIGINS):
                self._send_recordings_json(403, {"error": "origem não permitida"})
                return
            self.send_response(204)
            self._recordings_headers()
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._send_json(404, {"error": "not found"})

    def do_GET(self):
        if urlparse(self.path).path == "/api/supervision/summary":
            self._handle_supervision_summary()
        elif urlparse(self.path).path == "/api/queue":
            identity = self._require_queue_identity()
            if identity is None:
                return
            waiting = [
                item for item in state.waiting_list()
                if queue_tenant(item.get("queue")) == identity["tenant"]
            ]
            self._send_queue_json(200, {"waiting": waiting})
        elif urlparse(self.path).path == "/api/recordings":
            self._handle_list_recordings()
        elif urlparse(self.path).path == "/api/missed-calls":
            identity = self._require_queue_identity()
            if identity is None:
                return
            self._send_queue_json(200, {"missed_calls": scoped_monitoring_entries(
                missed_calls_log.list(limit=100), identity["tenant"],
            )[:20]})
        elif urlparse(self.path).path == "/api/fraud-alerts":
            identity = self._require_queue_identity()
            if identity is None:
                return
            self._send_queue_json(200, {"alerts": scoped_monitoring_entries(
                fraud_alerts_log.list(limit=100), identity["tenant"],
            )[:20]})
        elif urlparse(self.path).path == "/api/quality":
            self._handle_quality_query()
        elif urlparse(self.path).path == "/api/metrics/today":
            identity = self._require_queue_identity()
            if identity is None:
                return
            self._send_queue_json(200, tenant_daily_metrics.snapshot(identity["tenant"]))
        elif urlparse(self.path).path == "/api/metrics/sla/history":
            identity = self._require_queue_identity()
            if identity is None:
                return
            query = parse_qs(urlparse(self.path).query)
            tenant_records = [
                record for record in sla_history_store.load_all()
                if isinstance(record, dict)
                and queue_tenant(record.get("queue")) == identity["tenant"]
            ]
            records = filter_sla_history_by_date_range(
                tenant_records,
                start=query.get("start", [None])[0],
                end=query.get("end", [None])[0],
            )
            self._send_queue_json(200, {"by_date": summarize_sla_history_by_date(records)})
        elif urlparse(self.path).path == "/api/metrics/sla":
            identity = self._require_queue_identity()
            if identity is None:
                return
            scoped = {
                queue: stats for queue, stats in queue_sla_tracker.snapshot().items()
                if queue_tenant(queue) == identity["tenant"]
            }
            self._send_queue_json(200, {
                "threshold_seconds": SLA_THRESHOLD_SECONDS, "queues": scoped,
            })
        elif urlparse(self.path).path == "/api/reports/pauses":
            identity = self._require_queue_identity()
            if identity is None:
                return
            query = parse_qs(urlparse(self.path).query)
            tenant_prefix = identity["tenant"] + "-"
            records = filter_pause_records_by_date_range(
                [record for record in pause_history_store.load_all()
                 if isinstance(record, dict)
                 and isinstance(record.get("extension"), str)
                 and record["extension"].startswith(tenant_prefix)],
                start=query.get("start", [None])[0],
                end=query.get("end", [None])[0],
            )
            self._send_queue_json(200, {
                "by_reason": summarize_pause_time_by_reason(records),
                "by_extension": summarize_pause_time_by_extension(records),
                "total_records": len(records),
            })
        elif urlparse(self.path).path == "/api/extension-states":
            identity = self._require_queue_identity()
            if identity is None:
                return
            # Hint context is the authoritative namespace for BLF numbers
            # (which are reused across tenants, e.g. extension 1010).
            scoped = [entry for entry in extension_states.snapshot()
                      if entry.get("context") == identity["tenant"] + "-hints"]
            merged = merge_presence_into_states(scoped, load_presence(PRESENCE_PATH))
            merged = merge_pause_into_states(merged, agent_pause_store.snapshot())
            self._send_queue_json(200, {"extensions": merged})
        elif urlparse(self.path).path == "/api/presence":
            identity = self._require_queue_identity()
            if identity is None:
                return
            prefix = identity["tenant"] + "-"
            allowed_presence = {ext: entry for ext, entry in load_presence(PRESENCE_PATH).items()
                                if isinstance(ext, str) and ext.startswith(prefix)}
            self._send_queue_json(200, {"presence": allowed_presence})
        elif urlparse(self.path).path == "/api/reports":
            self._handle_reports()
        elif urlparse(self.path).path.startswith("/api/campaigns/"):
            self._handle_get_campaign()
        elif urlparse(self.path).path == "/api/campaigns":
            self._handle_list_campaigns()
        elif urlparse(self.path).path == "/api/callbacks":
            self._handle_list_callbacks()
        elif urlparse(self.path).path == "/api/satisfaction":
            self._handle_satisfaction_query()
        elif self.path.startswith("/recordings/"):
            self._serve_recording_file()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_supervision_summary(self):
        # Nunca confiar em tenant informado na query, payload ou rota.
        # A mesma política Bearer/Origin das filas é obrigatória.
        identity = self._require_queue_identity()
        if identity is None:
            return
        if identity.get("role") not in {"supervisor", "admin"}:
            self._send_queue_json(403, {"error": "supervisao restrita"})
            return
        tenant = identity["tenant"]
        try:
            result = build_supervision_summary(
                tenant,
                waiting=state.waiting_list(),
                extensions=extension_states.snapshot(),
                sla=queue_sla_tracker.snapshot(),
                missed=missed_calls_log.list(limit=100),
                fraud=fraud_alerts_log.list(limit=100),
                quality=quality_log.list(limit=100, only_poor=True),
                pauses=agent_pause_store.snapshot(),
                presence=load_presence(PRESENCE_PATH),
                threshold_seconds=SLA_THRESHOLD_SECONDS,
            )
            # Diagnósticos não herdam dados pessoais das fontes. Somente
            # supervisor/admin autenticado pode ler as 20 regras.
            result["diagnostics"] = evaluate_supervision_diagnostics(result)
        except (OSError, ValueError, TypeError, KeyError):
            # Se uma fonte local estiver corrompida, falhar fechado sem
            # imprimir nomes de arquivos ou conteúdo sensível no HTTP.
            self._send_queue_json(503, {"error": "supervisao indisponivel"})
            return
        self._send_queue_json(200, result)

    def _handle_quality_query(self):
        identity = self._require_queue_identity()
        if identity is None:
            return
        query = parse_qs(urlparse(self.path).query)
        only_poor = query.get("only_poor", ["false"])[0].lower() == "true"
        visible = scoped_monitoring_entries(
            quality_log.list(limit=100, only_poor=only_poor), identity["tenant"],
        )[:20]
        self._send_queue_json(200, {"quality_reports": visible})

    def _handle_satisfaction_query(self):
        identity = self._require_queue_identity()
        if identity is None:
            return
        query = parse_qs(urlparse(self.path).query)
        operator = query.get("operator", [None])[0]
        records = SurveyStore(SURVEY_PATH).query(
            operator=operator, tenant=identity["tenant"],
        )
        if query.get("group_by", [None])[0] == "operator":
            self._send_queue_json(200, {"by_operator": summarize_by_operator(records)})
        else:
            self._send_queue_json(200, {
                "average": average_score(records),
                "count": len(records),
                "distribution": score_distribution(records),
            })

    def _handle_reports(self):
        identity = self._require_queue_identity()
        if identity is None:
            return
        query = parse_qs(urlparse(self.path).query)
        start = query.get("start", [None])[0]
        end = query.get("end", [None])[0]
        operator = query.get("operator", [None])[0]
        group_field = query.get("group_by", [None])[0]

        # Ignore tenant supplied by client, even in a grouped report.
        records = call_log_store.query(
            start=start, end=end, operator=operator, tenant=identity["tenant"],
        )

        if group_field in ("operator", "tenant", "date"):
            self._send_queue_json(200, {"groups": group_by(records, group_field)})
        else:
            self._send_queue_json(200, aggregate(records))

    def _handle_list_recordings(self):
        access = self._require_recording_identity()
        if access is None:
            return
        policy, principal = access
        query = parse_qs(urlparse(self.path).query)
        all_recordings = list_recordings(
            RECORDINGS_DIR, limit=10000,
            caller_number=query.get("caller_number", [None])[0],
            destination=query.get("destination", [None])[0],
            start_date=query.get("start_date", [None])[0],
            end_date=query.get("end_date", [None])[0],
        )
        recordings = [
            entry for entry in all_recordings
            if can_read_recording(policy, principal, entry["filename"])
        ][:50]
        self._send_recordings_json(200, {"recordings": recordings})

    def _serve_recording_file(self):
        access = self._require_recording_identity()
        if access is None:
            return
        policy, principal = access
        filename = unquote(urlparse(self.path).path[len("/recordings/"):])
        # Responder 404 para qualquer gravação fora do escopo, sem
        # revelar sequer se o arquivo existe em outro tenant.
        if not can_read_recording(policy, principal, filename):
            self._send_recordings_json(404, {"error": "gravacao nao encontrada"})
            return
        # Abre por descritor relativo ao diretorio, sem seguir links.
        # Separar "verificar o caminho" de read_bytes() deixava uma
        # janela TOCTOU para trocar o arquivo por um symlink.
        opened = open_recording_file(RECORDINGS_DIR, filename)
        if opened is None:
            self._send_recordings_json(404, {"error": "gravacao nao encontrada"})
            return

        with opened:
            size = os.fstat(opened.fileno()).st_size
            content_type = "audio/wav" if filename.lower().endswith(".wav") else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self._recordings_headers()
            self.send_header("Content-Length", str(size))
            self.end_headers()
            remaining = size
            while remaining:
                chunk = opened.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

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
        elif re.fullmatch(r"/api/callbacks/[0-9a-f]{12}/cancel", self.path):
            self._handle_cancel_callback()
        elif urlparse(self.path).path.startswith("/api/presence/"):
            self._handle_set_presence()
        elif self.path == "/api/queue/pause":
            self._handle_set_pause()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_set_pause(self):
        identity = self._require_queue_identity()
        if identity is None:
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._send_queue_json(400, {"error": "Content-Length invalido"})
            return
        if not 0 < length <= 16384:
            self._send_queue_json(400, {"error": "tamanho de requisicao invalido"})
            return
        try:
            data = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError):
            self._send_queue_json(400, {"error": "JSON invalido"})
            return
        if not isinstance(data, dict):
            self._send_queue_json(400, {"error": "JSON deve ser objeto"})
            return
        ok, error, cleaned = validate_pause_request(data)
        if not ok:
            self._send_queue_json(400, {"error": error})
            return
        if not may_pickup(identity, cleaned["extension"]):
            self._send_queue_json(403, {"error": "ramal nao autorizado para pausa"})
            return
        if ami is None:
            self._send_queue_json(503, {"error": "AMI nao conectado"})
            return
        interface = f"PJSIP/{cleaned['extension']}"
        response = ami.pause_member(interface, cleaned["paused"], cleaned["reason"])
        if response.get("Response") == "Success":
            self._send_queue_json(200, {
                "extension": cleaned["extension"], "paused": cleaned["paused"],
                "reason": cleaned["reason"],
            })
        else:
            self._send_queue_json(502, {"error": "falha ao pausar/despausar"})


    def do_DELETE(self):
        if urlparse(self.path).path.startswith("/api/presence/"):
            self._handle_clear_presence()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_set_presence(self):
        identity = self._require_queue_identity()
        if identity is None:
            return
        extension = urlparse(self.path).path[len("/api/presence/"):]
        if not may_pickup(identity, extension):
            self._send_queue_json(403, {"error": "ramal nao autorizado para presenca"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._send_queue_json(400, {"error": "Content-Length invalido"})
            return
        if not 0 < length <= 16384:
            self._send_queue_json(400, {"error": "tamanho de requisicao invalido"})
            return
        try:
            data = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError):
            self._send_queue_json(400, {"error": "JSON invalido"})
            return
        if not isinstance(data, dict):
            self._send_queue_json(400, {"error": "JSON deve ser objeto"})
            return
        ok, error, cleaned = validate_presence_input(data)
        if not ok:
            self._send_queue_json(400, {"error": error})
            return
        entry = set_presence(PRESENCE_PATH, extension, cleaned["status"], cleaned["note"])
        self._send_queue_json(200, {"extension": extension, **entry})

    def _handle_clear_presence(self):
        identity = self._require_queue_identity()
        if identity is None:
            return
        extension = urlparse(self.path).path[len("/api/presence/"):]
        if not may_pickup(identity, extension):
            self._send_queue_json(403, {"error": "ramal nao autorizado para presenca"})
            return
        ok = clear_presence(PRESENCE_PATH, extension)
        self._send_queue_json(200, {"ok": ok})

    def _handle_pickup(self):
        identity = self._require_queue_identity()
        if identity is None:
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._send_queue_json(400, {"error": "Content-Length invalido"})
            return
        if length <= 0 or length > 16384:
            self._send_queue_json(400, {"error": "tamanho de requisicao invalido"})
            return
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeError):
            self._send_queue_json(400, {"error": "JSON invalido"})
            return

        if not isinstance(data, dict):
            self._send_queue_json(400, {"error": "JSON deve ser objeto"})
            return
        ok, error, channel, extension = validate_pickup_request(
            data, {"allowed_extensions": PICKUP_ALLOWED_EXTENSIONS}
        )
        if not ok:
            status = 403 if "autorizado" in error else 400
            self._send_queue_json(status, {"error": error})
            return

        if not may_pickup(identity, extension):
            self._send_queue_json(403, {"error": "ramal nao pertence a identidade autorizada"})
            return

        # Uma extensão autorizada não pode puxar fila de outra empresa.
        # O vínculo canal/fila vem do AMI, e nunca do corpo da requisição.
        queue_name = state.queue_for_channel(channel)
        if (queue_tenant(queue_name) != identity["tenant"]
                or not pickup_matches_queue(extension, queue_name)):
            self._send_queue_json(403, {"error": "pickup nao autorizado para esta fila"})
            return

        if ami is None:
            self._send_queue_json(503, {"error": "AMI nao conectado"})
            return

        response = ami.redirect_channel(channel, PICKUP_CONTEXT, exten=extension)
        if response.get("Response") == "Success":
            state.remove(channel)
            self._send_queue_json(200, {"ok": True})
        else:
            self._send_queue_json(502, {"error": "falha no redirect", "detail": response})

    def _handle_click_to_call(self):
        identity = self._require_queue_identity()
        if identity is None:
            return
        # Bearer é obrigatório além da chave operacional, em especial
        # para evitar que uma chave global acione o ramal de outro tenant.
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._send_queue_json(400, {"error": "Content-Length invalido"})
            return
        if not 0 < length <= 16384:
            self._send_queue_json(400, {"error": "tamanho invalido"})
            return
        try:
            data = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError):
            self._send_queue_json(400, {"error": "JSON invalido"})
            return
        if not isinstance(data, dict):
            self._send_queue_json(400, {"error": "JSON deve ser objeto"})
            return

        api_key = self.headers.get("X-Click-To-Call-Key", "")
        ok, error, extension, number = validate_click_to_call_request(data, api_key, CLICK_TO_CALL_CONFIG)
        if not ok:
            status = 403 if ("chave" in error or "autorizado" in error or "configurado" in error) else 400
            self._send_queue_json(status, {"error": error})
            return
        if not may_pickup(identity, extension):
            self._send_queue_json(403, {"error": "ramal nao autorizado para este tenant"})
            return
        if ami is None:
            self._send_queue_json(503, {"error": "AMI nao conectado"})
            return

        request_id = self.headers.get("X-Idempotency-Key")
        admitted, ticket = CTI_ADMISSION.reserve(
            identity["tenant"], extension, number, request_id)
        if admitted == "duplicate":
            self._send_queue_json(200, {"ok": True, "duplicate": True})
            return
        if admitted in ("pending", "conflict"):
            self._send_queue_json(409, {"error": "originação já registrada ou conflitante"})
            return
        if admitted == "limited":
            self._send_queue_json(429, {"error": "limite de originação atingido"})
            return
        if admitted != "reserved":
            self._send_queue_json(400, {"error": "idempotência ou origem inválida"})
            return

        action = build_originate_action(f"PJSIP/{extension}", number, CLICK_TO_CALL_CONTEXT)
        action["Account"] = identity["tenant"]
        action["Variable"] = "TENANT=" + identity["tenant"]
        try:
            response = ami.send_action(action)
        except (OSError, TimeoutError, ConnectionError):
            # Resposta AMI pode ter se perdido após Originate ser aceito.
            # O request-id permanece "uncertain" até expirar o TTL.
            CTI_ADMISSION.finish(ticket, "uncertain")
            self._send_queue_json(502, {"error": "resultado AMI desconhecido"})
            return
        accepted = isinstance(response, dict) and response.get("Response") == "Success"
        CTI_ADMISSION.finish(ticket, "accepted" if accepted else "rejected")
        if accepted:
            self._send_queue_json(200, {"ok": True, "duplicate": False})
        else:
            self._send_queue_json(502, {"error": "falha ao originar chamada"})

    def _require_campaign_api_key(self):
        """Autorização dupla: Bearer do tenant + chave de originação.

        A chave global sozinha nunca autoriza listar, criar ou discar.
        Agentes não podem iniciar discagem massiva/callbacks.
        """
        identity = self._require_queue_identity()
        if identity is None:
            return None
        if identity.get("role") not in {"supervisor", "admin"}:
            self._send_queue_json(403, {"error": "papel nao autorizado"})
            return None
        configured_key = CLICK_TO_CALL_CONFIG.get("api_key", "")
        api_key = self.headers.get("X-Click-To-Call-Key", "")
        if not configured_key:
            self._send_queue_json(503, {"error": "campanhas nao configuradas"})
            return None
        import hmac
        if not hmac.compare_digest(api_key, configured_key):
            self._send_queue_json(403, {"error": "chave de API invalida"})
            return None
        return identity

    def _read_campaign_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._send_queue_json(400, {"error": "Content-Length invalido"})
            return None
        if not 0 < length <= 65536:
            self._send_queue_json(400, {"error": "corpo invalido ou muito grande"})
            return None
        try:
            data = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError):
            self._send_queue_json(400, {"error": "JSON invalido"})
            return None
        if not isinstance(data, dict):
            self._send_queue_json(400, {"error": "JSON deve ser objeto"})
            return None
        return data

    def _handle_list_campaigns(self):
        identity = self._require_campaign_api_key()
        if identity is None:
            return
        campaigns = [
            c for c in load_campaigns(CAMPAIGNS_PATH)
            if c.get("tenant") == identity["tenant"]
            and may_pickup(identity, c.get("agent_extension"))
        ]
        summaries = [{**c, "summary": campaign_summary(c)} for c in campaigns]
        self._send_queue_json(200, {"campaigns": summaries})

    def _handle_get_campaign(self):
        identity = self._require_campaign_api_key()
        if identity is None:
            return
        path = urlparse(self.path).path
        campaign_id = path[len("/api/campaigns/"):]
        if not campaign_id or "/" in campaign_id:
            self._send_queue_json(404, {"error": "campanha nao encontrada"})
            return
        campaign = find_campaign(load_campaigns(CAMPAIGNS_PATH), campaign_id)
        if not campaign or campaign.get("tenant") != identity["tenant"] or not may_pickup(
                identity, campaign.get("agent_extension")):
            self._send_queue_json(404, {"error": "campanha nao encontrada"})
            return
        self._send_queue_json(200, {**campaign, "summary": campaign_summary(campaign)})

    def _handle_create_campaign(self):
        identity = self._require_campaign_api_key()
        if identity is None:
            return
        data = self._read_campaign_json()
        if data is None:
            return
        if not may_pickup(identity, data.get("agent_extension")):
            self._send_queue_json(403, {"error": "ramal de outra empresa"})
            return
        data["tenant"] = identity["tenant"]
        with outbound_lock(CAMPAIGNS_PATH):
            ok, error, campaign = create_campaign(CAMPAIGNS_PATH, data)
        if not ok:
            self._send_queue_json(400, {"error": error})
            return
        self._send_queue_json(201, campaign)

    def _handle_dial_next_contact(self):
        identity = self._require_campaign_api_key()
        if identity is None:
            return
        path = urlparse(self.path).path
        campaign_id = path[len("/api/campaigns/"):-len("/dial-next")].rstrip("/")
        if not campaign_id or "/" in campaign_id:
            self._send_queue_json(404, {"error": "campanha nao encontrada"})
            return
        campaign = find_campaign(load_campaigns(CAMPAIGNS_PATH), campaign_id)
        if not campaign or campaign.get("tenant") != identity["tenant"] or not may_pickup(
                identity, campaign.get("agent_extension")):
            self._send_queue_json(404, {"error": "campanha nao encontrada"})
            return

        contact = next_pending_contact(campaign)
        if not contact:
            self._send_queue_json(200, {"done": True, "message": "nenhum contato pendente"})
            return
        if ami is None:
            self._send_queue_json(503, {"error": "AMI nao conectado"})
            return

        # Claim precisa incluir a leitura do pendente: duas requisições
        # HTTP simultâneas não podem originar o mesmo contato.
        with outbound_lock(CAMPAIGNS_PATH):
            campaign = find_campaign(load_campaigns(CAMPAIGNS_PATH), campaign_id)
            if not campaign or campaign.get("tenant") != identity["tenant"] or not may_pickup(
                    identity, campaign.get("agent_extension")):
                self._send_queue_json(404, {"error": "campanha nao encontrada"})
                return
            contact = next_pending_contact(campaign)
            if not contact:
                self._send_queue_json(200, {"done": True, "message": "nenhum contato pendente"})
                return
            attempt_id = secrets.token_hex(16)
            ok, error = mark_contact_calling(
                CAMPAIGNS_PATH, campaign_id, contact["number"], attempt_id=attempt_id,
            )
            if not ok:
                self._send_queue_json(409, {"error": "contato nao reservado"})
                return
            action = build_originate_action(f"PJSIP/{campaign['agent_extension']}",
                                            contact["number"], CLICK_TO_CALL_CONTEXT)
            action["Account"] = identity["tenant"]
            action["Variable"] = "TENANT=" + identity["tenant"]
            action["ActionID"] = attempt_id
            action["ChannelId"] = "axe-" + attempt_id
            try:
                response = ami.send_action(action)
            except (OSError, TimeoutError, ConnectionError):
                self._send_queue_json(502, {"error": "resultado AMI incerto; conferir estado"})
                return
            if response.get("Response") == "Success":
                self._send_queue_json(200, {"ok": True, "dialing": contact["number"]})
            else:
                self._send_queue_json(502, {"error": "falha ao originar chamada"})

    def _read_callbacks_for_http(self):
        """Recusa catálogo ambíguo sem fingir que não há pedidos pendentes."""
        try:
            return load_callbacks(CALLBACKS_PATH)
        except (OSError, UnicodeError, ValueError):
            self._send_queue_json(503, {"error": "catalogo de callbacks indisponivel"})
            return None

    def _handle_list_callbacks(self):
        identity = self._require_campaign_api_key()
        if identity is None:
            return
        records = self._read_callbacks_for_http()
        if records is None:
            return
        callbacks = [c for c in records
                     if c.get("tenant") == identity["tenant"]]
        self._send_queue_json(200, {
            "callbacks": callbacks,
            "summary": summarize_callbacks(records, identity["tenant"]),
        })

    def _handle_cancel_callback(self):
        """Cancela pedido pendente, nunca chamada iniciada ou de outro tenant."""
        identity = self._require_campaign_api_key()
        if identity is None:
            return
        callback_id = self.path[len("/api/callbacks/"):-len("/cancel")]
        if callback_id.endswith("/"):
            callback_id = callback_id[:-1]
        try:
            with outbound_lock(CALLBACKS_PATH):
                ok, status = cancel_pending_callback(
                    CALLBACKS_PATH, callback_id, identity["tenant"],
                )
        except (OSError, UnicodeError, ValueError):
            self._send_queue_json(503, {"error": "catalogo de callbacks indisponivel"})
            return
        if not ok:
            if status == "not_found":
                self._send_queue_json(404, {"error": "callback nao encontrado"})
            else:
                self._send_queue_json(409, {"error": "callback ja reservado ou finalizado"})
            return
        self._send_queue_json(200, {"ok": True, "id": callback_id, "status": "cancelado"})

    def _handle_dial_next_callback(self):
        identity = self._require_campaign_api_key()
        if identity is None:
            return
        records = self._read_callbacks_for_http()
        if records is None:
            return
        callback = next_pending_callback([
            c for c in records if c.get("tenant") == identity["tenant"]
        ])
        if not callback:
            self._send_queue_json(200, {"done": True, "message": "nenhum callback pendente"})
            return
        from campaigns import sanitize_phone_number
        number = callback.get("caller_id_num")
        if (not isinstance(number, str) or sanitize_phone_number(number) != number):
            self._send_queue_json(400, {"error": "numero de callback invalido"})
            return
        if not CALLBACK_CONNECT_CONTEXT:
            self._send_queue_json(503, {"error": "contexto de callback nao configurado"})
            return
        if ami is None:
            self._send_queue_json(503, {"error": "AMI nao conectado"})
            return

        with outbound_lock(CALLBACKS_PATH):
            records = self._read_callbacks_for_http()
            if records is None:
                return
            callback = next_pending_callback([
                c for c in records if c.get("tenant") == identity["tenant"]
            ])
            if not callback:
                self._send_queue_json(200, {"done": True, "message": "nenhum callback pendente"})
                return
            number = callback.get("caller_id_num")
            if not isinstance(number, str) or sanitize_phone_number(number) != number:
                self._send_queue_json(400, {"error": "numero de callback invalido"})
                return
            attempt_id = secrets.token_hex(16)
            try:
                ok, error = mark_callback_calling(
                    CALLBACKS_PATH, callback["id"], attempt_id=attempt_id,
                )
            except (OSError, UnicodeError, ValueError):
                self._send_queue_json(503, {"error": "catalogo de callbacks indisponivel"})
                return
            if not ok:
                self._send_queue_json(409, {"error": "callback nao reservado"})
                return
            action = {
                "Action": "Originate",
                "Channel": f"PJSIP/{number}@gateway-tdm",
                "Context": CALLBACK_CONNECT_CONTEXT,
                "Exten": "s",
                "Priority": "1",
                "Async": "true",
                "Timeout": "30000",
                "CallerID": f'"Retorno de chamada" <{number}>',
                "Variable": "TENANT=" + identity["tenant"],
                "Account": identity["tenant"],
                "ActionID": attempt_id,
                "ChannelId": "axe-" + attempt_id,
            }
            try:
                response = ami.send_action(action)
            except (OSError, TimeoutError, ConnectionError):
                self._send_queue_json(502, {"error": "resultado AMI incerto; conferir estado"})
                return
            if response.get("Response") == "Success":
                self._send_queue_json(200, {"ok": True, "dialing": number})
            else:
                self._send_queue_json(502, {"error": "falha ao originar chamada"})

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
                print(f"[retenção] {len(deleted)} gravação(ões) expurgada(s)")
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
