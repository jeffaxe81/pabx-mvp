"""Rastreador de espera AMI: ciclo de vida, limites e isolamento AXE PABX.

Eventos são emitidos pelo Asterisk, mas podem ser reentregues, atrasar ou
chegar fora de ordem. Não criar nem encerrar chamadas aqui: é um espelho
em memória da fila, não a fonte autoritativa de bilhetagem/abandono.
"""
from collections import Counter, defaultdict
from math import isfinite
import re
import threading
import time

from pickup import queue_tenant

MAX_TRACKED_CALLS = 10000
MAX_WAITING_PER_QUEUE = 3000
DEFAULT_MAX_AGE_SECONDS = 6 * 3600
MAX_TENANTS_WITH_COUNTERS = 256
_UNIQUEID = re.compile(r"[A-Za-z0-9._-]{1,96}\Z")
_END_EVENTS = {
    "QueueCallerLeave": "left",
    "QueueCallerAbandon": "abandoned",
    "AgentConnect": "answered",
    "AgentDump": "agent_dump",
    "AgentComplete": "completed",
    "Hangup": "hung_up",
}


def _safe_caller_field(value, max_length):
    """CallerID/CallerIDName podem vir de tronco externo não confiável."""
    if (not isinstance(value, str) or len(value) > max_length
            or not value.isprintable()):
        return ""
    return value


def _valid_channel(channel):
    return (isinstance(channel, str) and 0 < len(channel) <= 160
            and channel.isprintable() and not any(c.isspace() for c in channel))


def _valid_uniqueid(value):
    return value is None or (isinstance(value, str)
                             and _UNIQUEID.fullmatch(value) is not None)


class QueueStateTracker:
    """Espelho seguro de chamadas aguardando por canal, fila e Uniqueid.

    As estatísticas são contadores locais, desde o início do processo, e
    nunca métricas contratuais nem eventos persistidos.
    """

    def __init__(self, max_waiting=MAX_TRACKED_CALLS,
                 max_per_queue=MAX_WAITING_PER_QUEUE,
                 max_age_seconds=DEFAULT_MAX_AGE_SECONDS, clock=None):
        if (type(max_waiting) is not int or not 1 <= max_waiting <= MAX_TRACKED_CALLS
                or type(max_per_queue) is not int or not 1 <= max_per_queue <= max_waiting
                or type(max_age_seconds) not in (int, float)
                or not isfinite(max_age_seconds) or not 1 <= max_age_seconds <= 86400):
            raise ValueError("limites do rastreador inválidos")
        self._waiting = {}
        self._lock = threading.RLock()
        self._max_waiting = max_waiting
        self._max_per_queue = max_per_queue
        self._max_age_seconds = max_age_seconds
        self._clock = clock or time.time
        self._counters = defaultdict(Counter)

    def _now(self):
        now = self._clock()
        return now if type(now) in (int, float) and isfinite(now) and now >= 0 else None

    def _count(self, tenant, field):
        # Proteger contra crescimento ilimitado de IDs de tenant vindos do AMI.
        if tenant in self._counters or len(self._counters) < MAX_TENANTS_WITH_COUNTERS:
            self._counters[tenant][field] += 1

    def _prune(self, now):
        if now is None:
            return
        for channel, row in list(self._waiting.items()):
            # Retrocesso do relógio não implica expiração da chamada.
            if now >= row["joined_at"] and now - row["joined_at"] > self._max_age_seconds:
                self._waiting.pop(channel, None)
                self._count(row["tenant"], "expired")

    def _end(self, event, kind):
        channel = event.get("Channel")
        if not _valid_channel(channel):
            return
        uniqueid = event.get("Uniqueid")
        if not _valid_uniqueid(uniqueid):
            return
        with self._lock:
            row = self._waiting.get(channel)
            if row is None:
                return
            queue_name = event.get("Queue")
            if kind != "hung_up" and (
                    not isinstance(queue_name, str)
                    or queue_name != row["queue"]):
                self._count(row["tenant"], "ignored_mismatched_queue")
                return
            if queue_name is not None and queue_name != row["queue"]:
                self._count(row["tenant"], "ignored_mismatched_queue")
                return
            # Nunca deixar um evento antigo remover a nova chamada que
            # reutilizou o mesmo nome de canal, especialmente entre tenants.
            if row["uniqueid"] is not None and uniqueid != row["uniqueid"]:
                self._count(row["tenant"], "ignored_mismatched_uniqueid")
                return
            self._waiting.pop(channel, None)
            self._count(row["tenant"], kind)

    def apply_event(self, event: dict):
        if not isinstance(event, dict):
            return
        kind = event.get("Event")
        if kind in _END_EVENTS:
            self._end(event, _END_EVENTS[kind])
            return
        if kind != "QueueCallerJoin":
            return
        channel, queue = event.get("Channel"), event.get("Queue")
        tenant = queue_tenant(queue)
        uniqueid = event.get("Uniqueid")
        if (not _valid_channel(channel) or tenant is None
                or not _valid_uniqueid(uniqueid)):
            return
        now = self._now()
        if now is None:
            return
        with self._lock:
            self._prune(now)
            previous = self._waiting.get(channel)
            if previous is not None:
                # A reentrega não pode reiniciar o tempo de espera.
                if previous["queue"] == queue and (
                        previous["uniqueid"] == uniqueid
                        or uniqueid is None and previous["uniqueid"] is None):
                    self._count(tenant, "duplicate_joins")
                    return
                # Um novo Join ambíguo não pode mover um canal de uma
                # empresa para outra sem Uniqueid diferente e verificável.
                if (previous["tenant"] != tenant and
                        (uniqueid is None or previous["uniqueid"] is None
                         or uniqueid == previous["uniqueid"])):
                    self._count(previous["tenant"], "blocked_ambiguous_requeue")
                    return
            else:
                if len(self._waiting) >= self._max_waiting:
                    self._count(tenant, "rejected_global_capacity")
                    return
                if sum(row["queue"] == queue for row in self._waiting.values()) >= self._max_per_queue:
                    self._count(tenant, "rejected_queue_capacity")
                    return
            self._waiting[channel] = {
                "channel": channel,
                "queue": queue,
                "tenant": tenant,
                "uniqueid": uniqueid,
                "caller_id_num": _safe_caller_field(event.get("CallerIDNum", ""), 64),
                "caller_id_name": _safe_caller_field(event.get("CallerIDName", ""), 128),
                "joined_at": now,
            }
            self._count(tenant, "requeues" if previous is not None else "joins")

    def waiting_list(self, queue_name=None, *, tenant=None):
        """Esperando por ordem FIFO, com filtro de tenant verificável.

        Não retorna Uniqueid nem tenant dentro de cada item por manter o
        contrato do webphone; leitura global só para servidor interno.
        """
        if tenant is not None and (
                not isinstance(tenant, str)
                or not re.fullmatch(r"t[1-9][0-9]*", tenant)):
            return []
        with self._lock:
            now = self._now()
            self._prune(now)
            items = [
                row for row in self._waiting.values()
                if (queue_name is None or row["queue"] == queue_name)
                and (tenant is None or row["tenant"] == tenant)
            ]
            items.sort(key=lambda row: (row["joined_at"], row["channel"]))
            return [{
                "channel": row["channel"],
                "queue": row["queue"],
                "caller_id_num": row["caller_id_num"],
                "caller_id_name": row["caller_id_name"],
                "waiting_seconds": max(0, int(now - row["joined_at"])) if now is not None else 0,
            } for row in items]

    def remove(self, channel, *, queue_name=None):
        """Remove após pickup; permite conferência da fila em caso de corrida."""
        if not _valid_channel(channel):
            return
        with self._lock:
            row = self._waiting.get(channel)
            if row is None or queue_name is not None and row["queue"] != queue_name:
                return
            self._waiting.pop(channel, None)
            self._count(row["tenant"], "removed_by_pickup")

    def queue_for_channel(self, channel):
        """Consulta a fila vinculada ao canal, após expurgar estados antigos."""
        if not _valid_channel(channel):
            return None
        with self._lock:
            self._prune(self._now())
            row = self._waiting.get(channel)
            return row["queue"] if row is not None else None

    def health_snapshot(self, tenant):
        """Saúde técnica por tenant, sem caller-id, canal, telefone ou Uniqueid."""
        if not isinstance(tenant, str) or not re.fullmatch(r"t[1-9][0-9]*", tenant):
            raise ValueError("tenant inválido")
        with self._lock:
            now = self._now()
            self._prune(now)
            rows = [row for row in self._waiting.values() if row["tenant"] == tenant]
            queues = Counter(row["queue"] for row in rows)
            waits = [max(0, int(now - row["joined_at"])) for row in rows] if now is not None else []
            counters = self._counters.get(tenant, Counter())
            return {
                "schema_version": 1,
                "tenant": tenant,
                "scope": "tenant_memory_only",
                "tracked_waiting": len(rows),
                "queues_with_waiting": len(queues),
                "max_queue_waiting": max(queues.values(), default=0),
                "longest_wait_seconds": max(waits, default=None),
                "events_joined": counters["joins"],
                "events_requeued": counters["requeues"],
                "events_abandoned": counters["abandoned"],
                "events_answered": counters["answered"],
                "events_left": counters["left"],
                "events_agent_dump": counters["agent_dump"],
                "events_agent_completed": counters["completed"],
                "events_hung_up": counters["hung_up"],
                "events_duplicate_join": counters["duplicate_joins"],
                "events_expired": counters["expired"],
                "events_rejected_capacity": counters["rejected_global_capacity"],
                "events_rejected_queue_capacity": counters["rejected_queue_capacity"],
                "events_rejected_cross_tenant_requeue": counters["blocked_ambiguous_requeue"],
                "events_ignored_queue_mismatch": counters["ignored_mismatched_queue"],
                "events_ignored_uniqueid_mismatch": counters["ignored_mismatched_uniqueid"],
                "events_removed_by_pickup": counters["removed_by_pickup"],
                "real_environment_homologated": False,
            }
