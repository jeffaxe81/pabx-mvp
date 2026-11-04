"""Gerenciamento dinâmico de agentes em filas Asterisk (somente voz).

Somente ações QueueAdd/QueueRemove/QueuePause, sem CLI ou comandos livres.
O pedido do HTTP é reconciliado com a identidade Bearer, com a allowlist
operacional de ramais e com as filas exatas do tenant. O estado exibido
é um espelho parcial de eventos AMI, não a verdade autoritativa da fila.
"""
import re
import threading
from collections import OrderedDict

from pickup import queue_tenant
from queue_access import may_pickup

_EXT = re.compile(r"t[1-9][0-9]*-[a-z0-9][a-z0-9-]{0,63}\Z")
_QUEUE = re.compile(r"fila-t[1-9][0-9]*(?:-(?:en|es))?\Z")
MAX_MEMBERS = 2000
EVENTS = {"QueueMemberAdded", "QueueMemberRemoved", "QueueMemberPause",
          "QueueMemberStatus", "QueueMemberPenalty"}


def valid_queue(value, tenant):
    return (isinstance(value, str) and len(value) <= 80
            and _QUEUE.fullmatch(value) is not None
            and queue_tenant(value) == tenant)


def valid_extension(value):
    return isinstance(value, str) and _EXT.fullmatch(value) is not None


def validate_member_change(payload, principal, allowed_extensions, operation):
    """Retorna (ok, error, cleaned). Rejeita campos extras por padrão."""
    if operation not in {"join", "leave", "pause"}:
        return False, "operacao nao permitida", None
    if (not isinstance(payload, dict) or not isinstance(principal, dict)
            or not isinstance(allowed_extensions, (list, tuple, set, frozenset))):
        return False, "requisicao de membro invalida", None

    fields = {"queue", "extension"}
    if operation == "join":
        fields |= {"penalty", "paused"}
    if operation == "pause":
        fields |= {"paused", "reason"}
    required = {"queue", "extension", "paused"} if operation == "pause" else {"queue", "extension"}
    if not required.issubset(payload) or not set(payload).issubset(fields):
        return False, "campos de membro invalidos", None
    tenant = principal.get("tenant")
    queue = payload.get("queue")
    extension = payload.get("extension")
    if (not isinstance(tenant, str) or not valid_queue(queue, tenant)
            or not valid_extension(extension)):
        return False, "fila ou ramal nao autorizado", None
    # Não confundir t1/t10; não permitir um PJSIP arbitrário criado
    # pelo corpo HTTP: o admin registra os ramais permitidos fora daqui.
    if extension not in allowed_extensions or not may_pickup(principal, extension):
        return False, "ramal nao cadastrado ou nao autorizado", None
    clean = {"queue": queue, "extension": extension}
    if operation == "join":
        penalty = payload.get("penalty", 0)
        paused = payload.get("paused", False)
        if type(penalty) is not int or not 0 <= penalty <= 10:
            return False, "penalty deve ser inteiro de 0 a 10", None
        if type(paused) is not bool:
            return False, "paused deve ser booleano", None
        clean.update(penalty=penalty, paused=paused)
    if operation == "pause":
        paused = payload.get("paused")
        reason = payload.get("reason", "")
        if type(paused) is not bool:
            return False, "paused deve ser booleano", None
        if (not isinstance(reason, str) or len(reason) > 80
                or not reason.isprintable() or ":" in reason):
            return False, "motivo de pausa invalido", None
        reason = reason.strip()
        if paused and not reason:
            return False, "motivo de pausa obrigatorio", None
        if not paused and reason:
            return False, "retorno de pausa nao aceita motivo", None
        clean.update(paused=paused, reason=reason)
    return True, None, clean


def member_ami_action(change, operation):
    """Constrói somente headers AMI aprovados; ActionID é da AMIClient."""
    queue = change["queue"]
    ext = change["extension"]
    interface = "PJSIP/" + ext
    if operation == "join":
        return {
            "Action": "QueueAdd", "Queue": queue, "Interface": interface,
            "Penalty": str(change["penalty"]),
            "Paused": "true" if change["paused"] else "false",
            "MemberName": ext, "StateInterface": interface,
        }
    if operation == "leave":
        return {"Action": "QueueRemove", "Queue": queue, "Interface": interface}
    if operation == "pause":
        action = {
            "Action": "QueuePause", "Queue": queue,
            "Interface": interface,
            "Paused": "true" if change["paused"] else "false",
        }
        if change["paused"]:
            action["Reason"] = change["reason"]
        return action
    raise ValueError("operacao de membro invalida")


def _event_extension(event):
    interface = event.get("Interface")
    if (not isinstance(interface, str) or not interface.startswith("PJSIP/")):
        return None
    ext = interface[6:]
    return ext if valid_extension(ext) else None


def _event_int(value, maximum):
    if type(value) is int and 0 <= value <= maximum:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 4:
        number = int(value)
        return number if number <= maximum else None
    return None


class QueueMemberTracker:
    """Último estado recebido por par fila/ramal, limite global e mutex.

    Um processo reiniciado não tem visão completa de membros estáticos.
    Só um evento de adição/estado cria um item novo. Remoções não criam.
    """

    def __init__(self, capacity=MAX_MEMBERS):
        if type(capacity) is not int or not 1 <= capacity <= MAX_MEMBERS:
            raise ValueError("limite de membros invalido")
        self._lock = threading.RLock()
        self._rows = OrderedDict()
        self._capacity = capacity
        self._seen_events = 0

    def apply_event(self, event):
        if not isinstance(event, dict) or event.get("Event") not in EVENTS:
            return
        queue = event.get("Queue")
        tenant = queue_tenant(queue)
        extension = _event_extension(event)
        if (tenant is None or not valid_queue(queue, tenant)
                or extension is None or not extension.startswith(tenant + "-")):
            return
        key = (queue, extension)
        with self._lock:
            kind = event["Event"]
            if kind == "QueueMemberRemoved":
                self._rows.pop(key, None)
                self._seen_events += 1
                return
            old = self._rows.get(key)
            if old is None and kind not in {"QueueMemberAdded", "QueueMemberStatus"}:
                return
            if old is None and len(self._rows) >= self._capacity:
                return
            row = dict(old or {
                "queue": queue, "extension": extension,
                "membership": "unknown", "paused": None,
                "penalty": None, "device_status": None,
            })
            membership = event.get("Membership")
            if membership in ("static", "dynamic", "realtime"):
                row["membership"] = membership
            paused = event.get("Paused")
            if paused in ("0", "1", 0, 1, False, True):
                row["paused"] = str(int(paused)) == "1"
            penalty = _event_int(event.get("Penalty"), 10)
            if penalty is not None:
                row["penalty"] = penalty
            device = _event_int(event.get("Status"), 8)
            if device is not None:
                row["device_status"] = device
            self._rows[key] = row
            self._rows.move_to_end(key)
            self._seen_events += 1

    def snapshot(self, principal):
        tenant = principal.get("tenant") if isinstance(principal, dict) else None
        role = principal.get("role") if isinstance(principal, dict) else None
        if (not isinstance(tenant, str) or not re.fullmatch(r"t[1-9][0-9]*", tenant)
                or role not in {"agent", "supervisor", "admin"}):
            raise ValueError("identidade invalida")
        extension = principal.get("extension") if role == "agent" else None
        if role == "agent" and (not valid_extension(extension)
                                or not extension.startswith(tenant + "-")):
            raise ValueError("identidade de agente invalida")
        with self._lock:
            rows = [
                dict(row) for (queue, ext), row in self._rows.items()
                if queue_tenant(queue) == tenant
                and (role != "agent" or ext == extension)
            ]
            return {
                "schema_version": 1, "tenant": tenant,
                "scope": "observed_ami_events_only",
                "complete_membership_inventory": False,
                "tracked_members": len(rows),
                "members": rows,
            }
