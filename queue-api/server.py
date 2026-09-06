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

AMI_HOST = os.environ.get("AMI_HOST", "127.0.0.1")
AMI_PORT = int(os.environ.get("AMI_PORT", "5038"))
AMI_USERNAME = os.environ.get("AMI_USERNAME", "queue-api")
AMI_SECRET = os.environ.get("AMI_SECRET", "troque_esta_senha_ami")
PICKUP_CONTEXT = os.environ.get("PICKUP_CONTEXT", "pickup-target")
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8090"))
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "/app/recordings")

state = QueueStateTracker()
ami = None  # inicializado em main(), None durante os testes automatizados


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
            length = int(self.headers.get("Content-Length", 0))
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._send_json(400, {"error": "JSON invalido"})
                return

            channel = data.get("channel")
            if not channel:
                self._send_json(400, {"error": "campo 'channel' obrigatorio"})
                return

            if ami is None:
                self._send_json(503, {"error": "AMI nao conectado"})
                return

            response = ami.redirect_channel(channel, PICKUP_CONTEXT)
            if response.get("Response") == "Success":
                state.remove(channel)
                self._send_json(200, {"ok": True})
            else:
                self._send_json(502, {"error": "falha no redirect", "detail": response})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass  # log padrão do BaseHTTPRequestHandler é barulhento demais


def main():
    global ami
    ami = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET, on_event=state.apply_event)
    ami.connect_and_login()
    ami.start_event_loop()

    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"queue-api ouvindo em :{HTTP_PORT}, conectado ao AMI em {AMI_HOST}:{AMI_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
