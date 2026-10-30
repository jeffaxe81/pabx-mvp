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
_CALLBACK_ID = re.compile(r"[0-9a-f]{12}\\Z")
_ATTEMPT_ID = re.compile(r"[0-9a-f]{32}\\Z")
_SOURCE_UNIQUEID = re.compile(r"[A-Za-z0-9._-]{1,96}\\Z")
_TENANT = re.compile(r"t[1-9][0-9]*\\Z")
_MAX_CATALOG_BYTES = 8 * 1024 * 1024
_MAX_CALLBACKS = 20000
_ACTIVE_STATUSES = frozenset({"pendente", "discando"})
_RESPONSE_STATUSES = frozenset({"Success", "Failure"})


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
    contact = _callback_contact(event.get("CallerIDNum"),
                                event.get("CallerIDName", ""))
    if contact is None:
        return None
    source = event.get("Uniqueid")
    if source is not None:
        if not isinstance(source, str) or _SOURCE_UNIQUEID.fullmatch(source) is None:
            return None
        contact["source_uniqueid"] = source
    return contact


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


def validate_callback_catalog(records):
    """Fail-closed for actionable callbacks; preserve completed legacy rows.

    Historical records may lack modern fields. Only actionable rows must
    have the exact correlation needed to authorize another Originate.
    """
    if not _catalog_has_unique_ids(records) or len(records) > _MAX_CALLBACKS:
        raise ValueError("catalogo de callbacks invalido ou excessivo")
    active_attempts = set()
    source_claims = set()
    for item in records:
        status = item.get("status")
        if not isinstance(status, str):
            raise ValueError("callback com status invalido")
        if status not in _ACTIVE_STATUSES:
            continue  # Retained history is not a dial authorization.
        cid = item.get("id")
        phone = item.get("caller_id_num")
        tenant = item.get("tenant")
        name = item.get("caller_id_name", "")
        when = item.get("requested_at")
        attempts = item.get("attempts")
        if (not isinstance(cid, str) or _CALLBACK_ID.fullmatch(cid) is None
                or not isinstance(phone, str) or _CALLBACK_PHONE.fullmatch(phone) is None
                or phone.startswith("+")
                or not isinstance(name, str) or len(name) > 80 or not name.isprintable()
                or tenant is not None and (
                    not isinstance(tenant, str) or _TENANT.fullmatch(tenant) is None)
                or type(when) not in (int, float) or not math.isfinite(when) or when < 0
                or type(attempts) is not int or not 0 <= attempts <= MAX_ATTEMPTS):
            raise ValueError("catalogo de callbacks com pedido "
                             + ("pendente" if status == "pendente" else "discando")
                             + " inconsistente")
        source = item.get("source_uniqueid")
        if source is not None:
            if (not isinstance(source, str)
                    or _SOURCE_UNIQUEID.fullmatch(source) is None):
                raise ValueError("callback com identificador de origem invalido")
            source_key = (tenant, source)
            if source_key in source_claims:
                raise ValueError("callback com origem AMI duplicada")
            source_claims.add(source_key)
        if status == "pendente":
            if attempts >= MAX_ATTEMPTS:
                raise ValueError("callback pendente com limite esgotado")
            continue
        # A DialEnd event may safely finalize only a correlated in-flight
        # attempt, not a record with a stale/missing AMI identity.
        attempt = item.get("attempt_id")
        started = item.get("last_attempt_at")
        if (attempts < 1 or not isinstance(attempt, str)
                or _ATTEMPT_ID.fullmatch(attempt) is None
                or item.get("channel_id") != "axe-" + attempt
                or type(started) not in (int, float)
                or not math.isfinite(started) or started < 0):
            raise ValueError("callback discando sem correlacao AMI valida")
        if attempt in active_attempts:
            raise ValueError("callback com identificador de tentativa duplicado")
        active_attempts.add(attempt)
        response = item.get("originate_response")
        if response is not None and (
                not isinstance(response, str) or response not in _RESPONSE_STATUSES):
            raise ValueError("callback com resposta AMI inconsistente")
        response_at = item.get("originate_response_at")
        if response_at is not None and (
                type(response_at) not in (int, float)
                or not math.isfinite(response_at) or response_at < 0):
            raise ValueError("callback com timestamp AMI inconsistente")
    return True


def load_callbacks(path) -> list:
    """Never treat an invalid outbound catalog as an empty callback queue."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("catalogo de callbacks em link simbolico")
    if not path.exists():
        return []
    if not path.is_file() or path.stat().st_size > _MAX_CATALOG_BYTES:
        raise ValueError("catalogo de callbacks nao regular ou excessivo")
    records = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_nonfinite_json_constant,
    )
    validate_callback_catalog(records)
    return records


def save_callbacks(path, callbacks: list):
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


def add_callback_request(path, caller_id_num: str, caller_id_name: str = "",
                         tenant=None, source_uniqueid=None):
    contact = _callback_contact(caller_id_num, caller_id_name)
    if contact is None:
        return None
    if tenant is not None:
        from monitoring_access import extension_tenant
        if not isinstance(tenant, str) or extension_tenant(tenant + "-recepcao") != tenant:
            return None
    if source_uniqueid is not None and (
            not isinstance(source_uniqueid, str)
            or _SOURCE_UNIQUEID.fullmatch(source_uniqueid) is None):
        return None
    callbacks = load_callbacks(path)
    # Asterisk may resend the SAME UserEvent after a reconnect. Its unique
    # source ID is a durable idempotency key inside one tenant, not a phone.
    if source_uniqueid is not None:
        matched = [item for item in callbacks
                   if item.get("tenant") == tenant
                   and item.get("source_uniqueid") == source_uniqueid]
        if matched:
            # Contradictory source reuse must never create another call.
            existing = matched[0]
            return existing if existing.get("caller_id_num") == contact["caller_id_num"] else None
    if len(callbacks) >= _MAX_CALLBACKS:
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
    if source_uniqueid is not None:
        entry["source_uniqueid"] = source_uniqueid
    callbacks.append(entry)
    save_callbacks(path, callbacks)
    return entry



CALLBACK_SUMMARY_STATUSES = (
    "pendente", "discando", "concluido", "cancelado", "esgotado",
)


def summarize_callbacks(callbacks, tenant, now=None):
    """Resumo gerencial sem dados pessoais, estritamente por empresa.

    Os registros legados sem tenant não são atribuídos por semelhança
    de número ou prefixo. Corrupção de ID torna o resultado indisponível.
    """
    if not _catalog_has_unique_ids(callbacks):
        raise ValueError("catalogo ambiguo")
    if not isinstance(tenant, str) or re.fullmatch(r"t[1-9][0-9]*", tenant) is None:
        raise ValueError("tenant invalido")
    scoped = [item for item in callbacks if item.get("tenant") == tenant]
    by_status = {status: 0 for status in CALLBACK_SUMMARY_STATUSES}
    by_status["outros"] = 0
    for item in scoped:
        status = item.get("status")
        if status in CALLBACK_SUMMARY_STATUSES:
            by_status[status] += 1
        else:
            by_status["outros"] += 1
    # Indicadores adicionais para a supervisão: todos derivados somente
    # do escopo autenticado, sem números ou nomes dos chamadores.
    now = time.time() if now is None else now
    if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
        raise ValueError("relogio de callbacks invalido")
    pending = [item for item in scoped if item.get("status") == "pendente"]
    oldest_pending = None
    if pending:
        requested = [item.get("requested_at") for item in pending]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
               for v in requested):
            raise ValueError("pedido pendente sem data valida")
        oldest_pending = max(0, int(now - min(requested)))
    return {
        "total": len(scoped), "by_status": by_status,
        "pending": by_status["pendente"],
        "dialing": by_status["discando"],
        "completed": by_status["concluido"],
        "cancelled": by_status["cancelado"],
        "oldest_pending_seconds": oldest_pending,
    }


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
