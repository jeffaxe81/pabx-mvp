"""
Chamada de retorno / callback (backlog #26). O cliente escolhe não
esperar na fila; o dialplan registra o pedido via UserEvent
(contexto [solicitar-callback] em extensions.conf), e este módulo
guarda/processa a lista - reaproveitando o mesmo padrão de
tentativas/status já usado em campaigns.py.

Lógica pura, sem rede - 100% testável.
"""
import json
import math
import re
import secrets
import time
from pathlib import Path

from outbound_safety import atomic_write_json

MAX_ATTEMPTS = 2  # menos tentativas que campanha - é o cliente esperando, não uma lista fria

DISPOSITION_TO_STATUS = {
    "ANSWER": "concluido",
    "BUSY": "ocupado",
    "NOANSWER": "sem_resposta",
    "CANCEL": "cancelado",
    "CONGESTION": "falha",
}

DIAL_STRING_RE = re.compile(r"PJSIP/(\d+)@gateway-tdm")


_CALLBACK_PHONE = re.compile(r"[+]?[0-9]{8,20}$")


def _callback_contact(number, name=""):
    """Aceita somente telefone discável e nome limitado, nunca JSON arbitrário."""
    if not isinstance(number, str) or not _CALLBACK_PHONE.fullmatch(number):
        return None
    digits = number.lstrip("+")
    if not 8 <= len(digits) <= 20:
        return None
    if not isinstance(name, str) or len(name) > 80 or not name.isprintable():
        name = ""
    return {"caller_id_num": digits, "caller_id_name": name}


def parse_callback_request_event(event: dict):
    """Rejeita UserEvent malformado antes de persistir ou discar."""
    if (not isinstance(event, dict) or event.get("Event") != "UserEvent"
            or event.get("UserEvent") != "CallbackRequest"):
        return None
    return _callback_contact(event.get("CallerIDNum"),
                             event.get("CallerIDName", ""))


def load_callbacks(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_callbacks(path, callbacks: list):
    atomic_write_json(path, callbacks)


def find_callback(callbacks: list, callback_id: str):
    return next((c for c in callbacks if c["id"] == callback_id), None)


def add_callback_request(path, caller_id_num: str, caller_id_name: str = "", tenant=None):
    contact = _callback_contact(caller_id_num, caller_id_name)
    if contact is None:
        return None
    if tenant is not None:
        from monitoring_access import extension_tenant
        if not isinstance(tenant, str) or extension_tenant(tenant + "-recepcao") != tenant:
            return None
    callbacks = load_callbacks(path)
    entry = {
        "id": secrets.token_hex(6),
        **contact,
        "status": "pendente",
        "attempts": 0,
        "requested_at": time.time(),
        "last_attempt_at": None,
    }
    if tenant is not None:
        entry["tenant"] = tenant
    callbacks.append(entry)
    save_callbacks(path, callbacks)
    return entry


def next_pending_callback(callbacks: list):
    """Seleciona FIFO somente com snapshot íntegro; corrupção nega discagem.

    O catálogo é persistido em JSON e pode ser alterado fora da API.
    Ignorar um item pendente inválido permitiria furar a ordem da fila.
    Nunca devolver itens com timestamp NaN, tipo inesperado ou número
    discável corrompido, nem misturar campos t1 e t10.
    """
    if not isinstance(callbacks, list):
        return None
    pending = []
    for item in callbacks:
        if not isinstance(item, dict):
            return None
        if item.get("status") != "pendente":
            continue
        when = item.get("requested_at")
        if (not isinstance(item.get("id"), str) or not item["id"]
                or type(when) not in (int, float) or not math.isfinite(when)
                or when < 0):
            return None
        if "caller_id_num" in item and _callback_contact(item["caller_id_num"]) is None:
            return None
        tenant = item.get("tenant")
        if tenant is not None and (
                not isinstance(tenant, str)
                or re.fullmatch(r"t[1-9][0-9]*", tenant) is None):
            return None
        pending.append(item)
    return min(pending, key=lambda item: item["requested_at"]) if pending else None


def mark_callback_calling(path, callback_id: str, attempt_id=None):
    callbacks = load_callbacks(path)
    callback = find_callback(callbacks, callback_id)
    if not callback:
        return False, f"callback '{callback_id}' não encontrado"

    if callback.get("status") != "pendente":
        return False, "callback ja reservado"
    attempt_id = attempt_id or secrets.token_hex(16)
    if not isinstance(attempt_id, str) or not re.fullmatch(r"[a-f0-9]{32}", attempt_id):
        return False, "id de tentativa invalido"
    callback["status"] = "discando"
    callback["attempts"] += 1
    callback["last_attempt_at"] = time.time()
    callback["attempt_id"] = attempt_id
    callback["channel_id"] = "axe-" + attempt_id
    save_callbacks(path, callbacks)
    return True, None


def mark_callback_result(path, callback_id: str, disposition: str):
    callbacks = load_callbacks(path)
    callback = find_callback(callbacks, callback_id)
    if not callback:
        return False, f"callback '{callback_id}' não encontrado"

    if callback["status"] != "discando":
        return False, "callback nao esta discando"

    # Evento AMI desconhecido não comprova tentativa concluída. Não
    # alterar estado nem liberar rediscagem em resultado ambíguo.
    if not isinstance(disposition, str) or disposition not in DISPOSITION_TO_STATUS:
        return False, "resultado AMI desconhecido"
    status = DISPOSITION_TO_STATUS[disposition]
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
