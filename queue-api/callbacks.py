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
from recording_access import read_regular_file_secure

MAX_CALLBACK_CATALOG_BYTES = 4 * 1024 * 1024
MAX_CALLBACK_RECORDS = 20000
_VALID_CALLBACK_STATES = {"pendente", "discando", "concluido", "cancelado", "esgotado"}

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


def _reject_duplicate_json_keys(pairs):
    """Um snapshot AMI com duas versões do mesmo campo é ambíguo."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("catalogo de callbacks com chave JSON duplicada")
        result[key] = value
    return result


def _reject_nonfinite_json_constant(value):
    raise ValueError("catalogo de callbacks com numero JSON nao finito")


def load_callbacks(path) -> list:
    """Recusa snapshots ambíguos sem os reinterpretar nem os corrigir.

    Nunca considerar um arquivo existente e corrompido como fila vazia:
    isso esconderia chamadas pendentes ou permitiria perda de dados.
    """
    path = Path(path)
    try:
        path.lstat()
    except FileNotFoundError:
        return []
    # read_regular_file_secure ancora os ancestrais em descritores
    # e recusa symlink, FIFO, dispositivo e arquivo excessivo.
    raw = read_regular_file_secure(path, MAX_CALLBACK_CATALOG_BYTES)
    records = json.loads(
        raw,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_nonfinite_json_constant,
    )
    if (not _catalog_has_unique_ids(records)
            or len(records) > MAX_CALLBACK_RECORDS):
        raise ValueError("catalogo de callbacks com ids inválidos ou volume excessivo")
    for record in records:
        status = record.get("status")
        tenant = record.get("tenant")
        if status not in _VALID_CALLBACK_STATES:
            raise ValueError("estado de callback inválido")
        if tenant is not None and (
                not isinstance(tenant, str)
                or re.fullmatch(r"t[1-9][0-9]*", tenant) is None):
            raise ValueError("empresa de callback histórico inválida")
        if status != "pendente":
            continue
        number = record.get("caller_id_num")
        contact = _callback_contact(number)
        when = record.get("requested_at")
        attempts = record.get("attempts")
        tenant = record.get("tenant")
        if (contact is None or contact["caller_id_num"] != number
                or type(when) not in (int, float) or not math.isfinite(when)
                or when < 0
                or type(attempts) is not int or not 0 <= attempts < MAX_ATTEMPTS
                or (tenant is not None
                    and (not isinstance(tenant, str)
                         or re.fullmatch(r"t[1-9][0-9]*", tenant) is None))):
            raise ValueError("catalogo de callbacks com pedido pendente inconsistente")
    return records


def save_callbacks(path, callbacks: list):
    if (not _catalog_has_unique_ids(callbacks)
            or len(callbacks) > MAX_CALLBACK_RECORDS):
        raise ValueError("catálogo de callbacks inválido ou volumoso")
    try:
        encoded = json.dumps(callbacks, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("catálogo de callbacks não serializável") from exc
    if len(encoded) > MAX_CALLBACK_CATALOG_BYTES:
        raise ValueError("catálogo de callbacks ultrapassa limite de armazenamento")
    atomic_write_json(path, callbacks)


def _catalog_has_unique_ids(callbacks):
    """Impedir referências ambíguas inclusive entre tenants distintos."""
    if not isinstance(callbacks, list):
        return False
    ids = []
    for item in callbacks:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                or not item["id"]):
            return False
        ids.append(item["id"])
    return len(ids) == len(set(ids))


def find_callback(callbacks: list, callback_id: str):
    """Nunca escolher o primeiro de dois pedidos com o mesmo ID."""
    if not isinstance(callback_id, str) or not _catalog_has_unique_ids(callbacks):
        return None
    return next((item for item in callbacks if item["id"] == callback_id), None)


def add_callback_request(path, caller_id_num: str, caller_id_name: str = "", tenant=None):
    contact = _callback_contact(caller_id_num, caller_id_name)
    if contact is None:
        return None
    if tenant is not None:
        from monitoring_access import extension_tenant
        if not isinstance(tenant, str) or extension_tenant(tenant + "-recepcao") != tenant:
            return None
    callbacks = load_callbacks(path)
    if not _catalog_has_unique_ids(callbacks):
        return None
    existing_ids = {item["id"] for item in callbacks}
    callback_id = None
    for _ in range(20):
        candidate = secrets.token_hex(6)
        if candidate not in existing_ids:
            callback_id = candidate
            break
    if callback_id is None:
        return None
    entry = {
        "id": callback_id,
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
    if not _catalog_has_unique_ids(callbacks):
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



def cancel_pending_callback(path, callback_id, tenant):
    """Cancela somente pedido pendente da empresa autenticada.

    O chamador precisa manter outbound_lock(path) durante toda a
    leitura, validação e escrita; outra requisição não pode reservar
    simultaneamente o mesmo pedido. Não encerra chamadas já originadas.
    """
    if (not isinstance(callback_id, str)
            or re.fullmatch(r"[0-9a-f]{12}", callback_id) is None
            or not isinstance(tenant, str)
            or re.fullmatch(r"t[1-9][0-9]*", tenant) is None):
        return False, "not_found"
    callbacks = load_callbacks(path)
    callback = find_callback(callbacks, callback_id)
    if callback is None or callback.get("tenant") != tenant:
        return False, "not_found"
    if callback.get("status") != "pendente":
        return False, "not_pending"
    callback["status"] = "cancelado"
    callback["cancelled_at"] = time.time()
    save_callbacks(path, callbacks)
    return True, "cancelado"

def mark_callback_calling(path, callback_id: str, attempt_id=None):
    callbacks = load_callbacks(path)
    callback = find_callback(callbacks, callback_id)
    if not callback:
        return False, f"callback '{callback_id}' não encontrado"

    if callback.get("status") != "pendente":
        return False, "callback ja reservado"
    attempts = callback.get("attempts")
    if type(attempts) is not int or not 0 <= attempts < MAX_ATTEMPTS:
        return False, "contador de tentativas do callback invalido"
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

    if callback.get("status") != "discando":
        return False, "callback nao esta discando"
    attempts = callback.get("attempts")
    if type(attempts) is not int or not 1 <= attempts <= MAX_ATTEMPTS:
        return False, "contador de tentativas do callback invalido"

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
