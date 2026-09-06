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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ami_client import AMIClient
from queue_state import QueueStateTracker
from recordings import list_recordings, safe_recording_path
from missed_calls import parse_missed_call_event, MissedCallsLog
from notifiers import dispatch_notifications
from click_to_call import build_originate_action, validate_click_to_call_request
from metrics import DailyMetrics
from pickup import validate_pickup_request
from extension_states import ExtensionStateTracker

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

state = QueueStateTracker()
missed_calls_log = MissedCallsLog()
daily_metrics = DailyMetrics()
extension_states = ExtensionStateTracker()
ami = None  # inicializado em main(), None durante os testes automatizados


def handle_ami_event(event: dict):
    """Callback único do AMI: alimenta fila, chamadas perdidas, métricas e estado dos ramais."""
    state.apply_event(event)
    daily_metrics.apply_cdr_event(event)
    extension_states.apply_event(event)

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
            self._send_json(200, {"recordings": list_recordings(RECORDINGS_DIR)})
        elif self.path.startswith("/api/missed-calls"):
            self._send_json(200, {"missed_calls": missed_calls_log.list()})
        elif self.path.startswith("/api/metrics/today"):
            self._send_json(200, daily_metrics.snapshot())
        elif self.path.startswith("/api/extension-states"):
            self._send_json(200, {"extensions": extension_states.snapshot()})
        elif self.path.startswith("/recordings/"):
            self._serve_recording_file()
        else:
            self._send_json(404, {"error": "not found"})

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

    def log_message(self, format, *args):
        pass  # log padrão do BaseHTTPRequestHandler é barulhento demais


def main():
    global ami
    ami = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET, on_event=handle_ami_event)
    ami.connect_and_login()
    ami.start_event_loop()

    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"queue-api ouvindo em :{HTTP_PORT}, conectado ao AMI em {AMI_HOST}:{AMI_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
