"""
Serviço de IA (backlog #21/#22/#23): transcrição, resumo e análise de
sentimento das gravações de chamada. DESLIGADO POR PADRÃO
(AI_FEATURES_ENABLED=false) - processamento de IA local tem custo
computacional real (CPU/tempo), diferente do resto das integrações
"grátis" deste projeto.

Quando ligado, varre periodicamente a pasta de gravações (mesma do
manual 09) em busca de arquivos ainda não processados, e processa um
de cada vez (sem paralelismo de propósito - Whisper/Llama em CPU já
competem por recursos sozinhos).
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from store import TranscriptStore
from pipeline import process_recording
from recordings_scanner import list_unprocessed_recordings
from intent_classifier import build_intent_prompt, parse_intent_response, intent_to_extension
from transcription import transcribe_audio
from llm_client import generate as llm_generate

HTTP_PORT = int(os.environ.get("HTTP_PORT", "8092"))
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "/app/recordings")
TRANSCRIPTS_PATH = os.environ.get("TRANSCRIPTS_PATH", "/app/data/transcripts.jsonl")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")

# Desligado por padrão - processamento de IA tem custo computacional
# real (minutos de CPU por chamada em hardware modesto), diferente do
# resto das integrações deste projeto.
AI_FEATURES_ENABLED = os.environ.get("AI_FEATURES_ENABLED", "false").lower() == "true"
SCAN_INTERVAL_SECONDS = int(os.environ.get("SCAN_INTERVAL_SECONDS", "60"))

store = TranscriptStore(TRANSCRIPTS_PATH)


def process_next_pending():
    """Processa UMA gravação pendente por vez (sem paralelismo, ver docstring do módulo)."""
    already_processed = {r["filename"] for r in store.load_all()}
    pending = list_unprocessed_recordings(RECORDINGS_DIR, already_processed)
    if not pending:
        return None

    filename = pending[0]
    recording_path = Path(RECORDINGS_DIR) / filename
    result = process_recording(
        recording_path, filename, OLLAMA_URL,
        model=OLLAMA_MODEL, whisper_model_size=WHISPER_MODEL_SIZE,
    )
    store.append(result)
    return result


def scan_loop():
    while True:
        if AI_FEATURES_ENABLED:
            try:
                result = process_next_pending()
                if result:
                    print(f"[ai-worker] processado: {result['filename']}")
            except Exception as exc:  # noqa: BLE001
                print(f"[ai-worker] falha ao processar gravação: {exc}")
        time.sleep(SCAN_INTERVAL_SECONDS)


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/api/transcripts/"):
            filename = self.path[len("/api/transcripts/"):]
            record = store.find_by_filename(filename)
            if record:
                self._send_json(200, record)
            else:
                self._send_json(404, {"error": "ainda não processado ou não encontrado"})
        elif self.path.startswith("/api/transcripts"):
            query = parse_qs(urlparse(self.path).query)
            limit = int(query.get("limit", ["50"])[0])
            self._send_json(200, {"transcripts": store.load_all()[-limit:], "ai_enabled": AI_FEATURES_ENABLED})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/api/process/"):
            if not AI_FEATURES_ENABLED:
                self._send_json(503, {"error": "recursos de IA desabilitados (AI_FEATURES_ENABLED=false)"})
                return
            filename = self.path[len("/api/process/"):]
            recording_path = Path(RECORDINGS_DIR) / filename
            if not recording_path.is_file():
                self._send_json(404, {"error": "gravação não encontrada"})
                return
            result = process_recording(
                recording_path, filename, OLLAMA_URL,
                model=OLLAMA_MODEL, whisper_model_size=WHISPER_MODEL_SIZE,
            )
            store.append(result)
            self._send_json(200, result)
        elif self.path == "/api/classify-intent":
            self._handle_classify_intent()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_classify_intent(self):
        """
        Usado pelo script AGI do atendente virtual (backlog #24, ver
        manual 37): recebe o caminho de uma gravação curta (o cliente
        descrevendo o motivo da ligação), transcreve, classifica a
        intenção, e devolve o ramal de destino já calculado - o AGI só
        precisa aplicar isso como variável de canal.
        """
        if not AI_FEATURES_ENABLED:
            self._send_json(503, {"error": "recursos de IA desabilitados (AI_FEATURES_ENABLED=false)"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "JSON inválido"})
            return

        recording_path = Path(RECORDINGS_DIR) / data.get("filename", "")
        if not recording_path.is_file():
            self._send_json(404, {"error": "gravação não encontrada"})
            return

        transcript = transcribe_audio(recording_path, model_size=WHISPER_MODEL_SIZE)
        if not transcript.strip():
            # Sem transcrição não dá pra classificar - cai no destino
            # seguro (fila geral) em vez de travar a chamada.
            self._send_json(200, {"transcript": "", "intent": "outro", "extension": intent_to_extension("outro")})
            return

        raw_response = llm_generate(OLLAMA_URL, build_intent_prompt(transcript), model=OLLAMA_MODEL)
        intent = parse_intent_response(raw_response)
        self._send_json(200, {
            "transcript": transcript,
            "intent": intent,
            "extension": intent_to_extension(intent),
        })


def main():
    if AI_FEATURES_ENABLED:
        threading.Thread(target=scan_loop, daemon=True).start()
    else:
        print("[ai-worker] AI_FEATURES_ENABLED=false - só a API de consulta está ativa, nada é processado sozinho")

    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"ai-worker ouvindo em :{HTTP_PORT} (AI_FEATURES_ENABLED={AI_FEATURES_ENABLED})")
    server.serve_forever()


if __name__ == "__main__":
    main()
