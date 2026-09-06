"""
Chamada de retorno / callback (backlog #26). O cliente escolhe não
esperar na fila; o dialplan registra o pedido via UserEvent
(contexto [solicitar-callback] em extensions.conf), e este módulo
guarda/processa a lista - reaproveitando o mesmo padrão de
tentativas/status já usado em campaigns.py.

Lógica pura, sem rede - 100% testável.
"""
import json
import re
import secrets
import time
from pathlib import Path

MAX_ATTEMPTS = 2  # menos tentativas que campanha - é o cliente esperando, não uma lista fria

DISPOSITION_TO_STATUS = {
    "ANSWER": "concluido",
    "BUSY": "ocupado",
    "NOANSWER": "sem_resposta",
    "CANCEL": "cancelado",
    "CONGESTION": "falha",
}

DIAL_STRING_RE = re.compile(r"PJSIP/(\d+)@gateway-tdm")


def parse_callback_request_event(event: dict):
    """Extrai os dados de um evento AMI UserEvent/CallbackRequest, ou None se não for esse."""
    if event.get("Event") != "UserEvent" or event.get("UserEvent") != "CallbackRequest":
        return None

    caller_id_num = event.get("CallerIDNum")
    if not caller_id_num:
        return None

    return {
        "caller_id_num": caller_id_num,
        "caller_id_name": event.get("CallerIDName", ""),
    }


def load_callbacks(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_callbacks(path, callbacks: list):
    Path(path).write_text(json.dumps(callbacks, indent=2, ensure_ascii=False), encoding="utf-8")


def find_callback(callbacks: list, callback_id: str):
    return next((c for c in callbacks if c["id"] == callback_id), None)


def add_callback_request(path, caller_id_num: str, caller_id_name: str = ""):
    callbacks = load_callbacks(path)
    entry = {
        "id": secrets.token_hex(6),
        "caller_id_num": caller_id_num,
        "caller_id_name": caller_id_name,
        "status": "pendente",
        "attempts": 0,
        "requested_at": time.time(),
        "last_attempt_at": None,
    }
    callbacks.append(entry)
    save_callbacks(path, callbacks)
    return entry


def next_pending_callback(callbacks: list):
    """
    Mais antigo primeiro (FIFO) - é isso que garante que o cliente
    "não perde a vez" mesmo tendo saído da fila.
    """
    pending = [c for c in callbacks if c["status"] == "pendente"]
    if not pending:
        return None
    return min(pending, key=lambda c: c["requested_at"])


def mark_callback_calling(path, callback_id: str):
    callbacks = load_callbacks(path)
    callback = find_callback(callbacks, callback_id)
    if not callback:
        return False, f"callback '{callback_id}' não encontrado"

    callback["status"] = "discando"
    callback["attempts"] += 1
    callback["last_attempt_at"] = time.time()
    save_callbacks(path, callbacks)
    return True, None


def mark_callback_result(path, callback_id: str, disposition: str):
    callbacks = load_callbacks(path)
    callback = find_callback(callbacks, callback_id)
    if not callback:
        return False, f"callback '{callback_id}' não encontrado"

    status = DISPOSITION_TO_STATUS.get(disposition, "falha")
    if status != "concluido" and callback["attempts"] < MAX_ATTEMPTS:
        status = "pendente"
    elif status != "concluido":
        status = "esgotado"

    callback["status"] = status
    save_callbacks(path, callbacks)
    return True, None


def extract_dialed_number(event: dict):
    """Mesma extração usada em campaigns.py - a partir do Dialstring do DialEnd."""
    dialstring = event.get("Dialstring", "")
    match = DIAL_STRING_RE.search(dialstring)
    if match:
        return match.group(1)
    return event.get("DestExten") or None
