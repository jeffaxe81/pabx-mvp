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
        if type(max_size) is not int or not 1 <= max_size <= 10000:
            raise ValueError("limite de historico invalido")
        self._entries = []
        self._max_size = max_size

    def append(self, missed_call: dict):
        if not isinstance(missed_call, dict):
            return False
        # Lista explícita: não copiar campos arbitrários recebidos de AMI/APIs,
        # evitando objetos aninhados, dados privados e payloads excessivos.
        entry = {}
        for name, maximum in (("caller_id_num", 64), ("caller_id_name", 100),
                              ("destination", 96)):
            if name in missed_call:
                entry[name] = _safe_ami_text(
                    missed_call[name], "desconhecido" if name == "caller_id_num" else "",
                    maximum,
                )
        for name in ("reason", "source"):
            if name in missed_call:
                entry[name] = _safe_ami_text(missed_call[name], max_length=64)
        entry["timestamp"] = time.time()
        self._entries.append(entry)
        if len(self._entries) > self._max_size:
            self._entries.pop(0)
        return True

    def list(self, limit=20):
        """Mais recente primeiro, com cópias para não alterar o histórico."""
        if type(limit) is not int or limit <= 0:
            return []
        return [dict(record) for record in reversed(self._entries)][
            :min(limit, self._max_size)]
