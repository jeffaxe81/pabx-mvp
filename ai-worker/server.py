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
import uuid
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from store import TranscriptStore
from pipeline import process_recording
from recordings_scanner import list_unprocessed_recordings
from intent_classifier import build_intent_prompt, parse_intent_response, intent_to_extension, build_confirmation_phrase
from transcription import transcribe_audio
from llm_client import generate as llm_generate
from tts_service import validate_tts_request, ENGINE_PIPER, ENGINE_XTTS
import piper_engine
import xtts_engine

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

# TTS (backlog #48) - Piper é sempre disponível quando AI_FEATURES_ENABLED
# está ligado (licença MIT, seguro comercialmente). XTTS-v2 tem uma
# flag PRÓPRIA e separada, desligada por padrão - licença não-comercial
# (Coqui Public Model License), ver piper_engine.py/xtts_engine.py e
# docs/manual-48 antes de ativar.
TTS_XTTS_ENABLED = os.environ.get("TTS_XTTS_ENABLED", "false").lower() == "true"
SOUNDS_OUTPUT_DIR = os.environ.get("SOUNDS_OUTPUT_DIR", "/app/sounds-output")

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
        elif self.path == "/api/tts":
            self._handle_tts()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_tts(self):
        """
        Síntese de voz (backlog #48) - gera um arquivo .wav a partir
        de texto digitado, em vez de precisar de locutor/estúdio.
        Piper (padrão) sempre disponível quando AI_FEATURES_ENABLED
        está ligado; XTTS-v2 exige TTS_XTTS_ENABLED também (ver aviso
        de licenciamento em xtts_engine.py e docs/manual-48).
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

        ok, error, cleaned = validate_tts_request(data, xtts_enabled=TTS_XTTS_ENABLED)
        if not ok:
            self._send_json(400, {"error": error})
            return

        filename = cleaned["filename"] or f"tts-{uuid.uuid4().hex}.wav"
        output_path = Path(SOUNDS_OUTPUT_DIR) / filename
        Path(SOUNDS_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

        try:
            engine_module = piper_engine if cleaned["engine"] == ENGINE_PIPER else xtts_engine
            engine_module.synthesize(cleaned["text"], cleaned["language"], output_path)
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao sintetizar áudio: {exc}"})
            return

        self._send_json(200, {"filename": filename, "engine": cleaned["engine"], "language": cleaned["language"]})

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
            confirmation = self._synthesize_confirmation("outro")
            self._send_json(200, {
                "transcript": "", "intent": "outro", "extension": intent_to_extension("outro"),
                "confirmation_filename": confirmation,
            })
            return

        raw_response = llm_generate(OLLAMA_URL, build_intent_prompt(transcript), model=OLLAMA_MODEL)
        intent = parse_intent_response(raw_response)
        confirmation = self._synthesize_confirmation(intent)
        self._send_json(200, {
            "transcript": transcript,
            "intent": intent,
            "extension": intent_to_extension(intent),
            "confirmation_filename": confirmation,
        })

    def _synthesize_confirmation(self, intent: str):
        """
        Gera o áudio de confirmação falada (backlog #48, fase 2) via
        Piper - best-effort: se a síntese falhar por qualquer motivo,
        devolve None em vez de travar a resposta inteira. O atendente
        virtual continua funcionando sem a confirmação falada, só sem
        esse toque a mais.
        """
        try:
            phrase = build_confirmation_phrase(intent)
            filename = f"tts-{uuid.uuid4().hex}.wav"
            output_path = Path(SOUNDS_OUTPUT_DIR) / filename
            Path(SOUNDS_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
            piper_engine.synthesize(phrase, "pt", output_path)
            return filename
        except Exception:  # noqa: BLE001
            return None


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
