#!/usr/bin/env python3
"""
Atendente virtual com IA (backlog #24) - script AGI chamado pelo
dialplan (contexto [atendente-virtual] em extensions.conf). Grava
o cliente descrevendo o motivo da ligação, manda pro ai-worker
classificar a intenção (vendas/suporte/outro), e define a variável
INTENT_DESTINO que o dialplan usa pra rotear.

É a parte NÃO testável automaticamente deste recurso (fala de verdade
com o processo Asterisk via stdin/stdout AGI, e com o ai-worker via
HTTP) - a lógica de parsing/montagem de comandos está isolada em
agi_protocol.py, que tem cobertura de teste completa. Ver manual 37.
"""
import json
import os
import sys
import urllib.request

from agi_protocol import parse_agi_env, build_record_command, build_set_variable_command, parse_agi_response

AI_WORKER_URL = os.environ.get("AI_WORKER_URL", "http://ai-worker:8092")
RECORDINGS_DIR = os.environ.get("AGI_RECORDINGS_DIR", "/var/spool/asterisk/monitor")
FALLBACK_EXTENSION = "1000"  # fila geral - nunca deixa a chamada sem destino


def read_agi_env():
    lines = []
    while True:
        line = sys.stdin.readline()
        if not line or line.strip() == "":
            break
        lines.append(line)
    return parse_agi_env(lines)


def send_agi_command(command: str) -> dict:
    sys.stdout.write(command + "\n")
    sys.stdout.flush()
    response_line = sys.stdin.readline()
    return parse_agi_response(response_line)


def classify_intent(filename: str) -> str:
    """Chama o ai-worker; em qualquer falha, cai no destino seguro (fila geral)."""
    try:
        body = json.dumps({"filename": filename}).encode("utf-8")
        request = urllib.request.Request(
            f"{AI_WORKER_URL}/api/classify-intent",
            data=body, method="POST", headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("extension", FALLBACK_EXTENSION)
    except Exception as exc:  # noqa: BLE001
        print(f"[atendente-virtual] falha ao classificar intenção: {exc}", file=sys.stderr)
        return FALLBACK_EXTENSION


def main():
    env = read_agi_env()
    unique_id = env.get("agi_uniqueid", "sem-id").replace(".", "-")
    filename = f"intake-{unique_id}.wav"
    recording_path = os.path.join(RECORDINGS_DIR, f"intake-{unique_id}")

    send_agi_command(build_record_command(recording_path, audio_format="wav", timeout_ms=8000))

    destination = classify_intent(filename)
    send_agi_command(build_set_variable_command("INTENT_DESTINO", destination))


if __name__ == "__main__":
    main()
