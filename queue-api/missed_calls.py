"""
Detecta chamadas perdidas a partir de eventos AMI. Lógica pura -
recebe um dict de evento, devolve um registro normalizado de chamada
perdida ou None. Nenhuma rede aqui, 100% testável.

Duas fontes de "chamada perdida":
1. DialEnd com DialStatus != ANSWER - cobre chamada direta (ramal
   1000), chamada entre ramais, e a chamada puxada da fila
   (pickup-target) - qualquer Dial() que não foi atendido.
2. QueueCallerAbandon - o cliente desistiu e desligou enquanto
   esperava na fila, antes de qualquer agente atender.
"""
import time

MISSED_DIAL_STATUSES = {"NOANSWER", "BUSY", "CANCEL", "CONGESTION"}


def _safe_ami_text(value, fallback="", max_length=100):
    """Não propagar estruturas ou CR/LF de cabeçalhos AMI para relatórios."""
    if (not isinstance(value, str) or not value or len(value) > max_length
            or not value.isprintable()):
        return fallback
    return value


def parse_missed_call_event(event: dict):
    if not isinstance(event, dict):
        return None
    event_name = event.get("Event")

    if event_name == "DialEnd":
        status = event.get("DialStatus")
        if not isinstance(status, str) or status not in MISSED_DIAL_STATUSES:
            return None
        return {
            "caller_id_num": _safe_ami_text(event.get("CallerIDNum"), "desconhecido", 64),
            "caller_id_name": _safe_ami_text(event.get("CallerIDName"), max_length=100),
            "destination": _safe_ami_text(
                event.get("DestCallerIDNum") or event.get("Exten"), max_length=96),
            "reason": status,
            "source": "dial",
        }

    if event_name == "QueueCallerAbandon":
        return {
            "caller_id_num": _safe_ami_text(event.get("CallerIDNum"), "desconhecido", 64),
            "caller_id_name": _safe_ami_text(event.get("CallerIDName"), max_length=100),
            "destination": _safe_ami_text(event.get("Queue"), max_length=96),
            "reason": "ABANDONED",
            "source": "queue",
        }

    return None


class MissedCallsLog:
    """Histórico em memória das últimas chamadas perdidas."""

    def __init__(self, max_size=100):
        self._entries = []
        self._max_size = max_size

    def append(self, missed_call: dict):
        entry = dict(missed_call)
        entry["timestamp"] = time.time()
        self._entries.append(entry)
        if len(self._entries) > self._max_size:
            self._entries.pop(0)

    def list(self, limit=20):
        """Mais recente primeiro."""
        return list(reversed(self._entries))[:limit]
