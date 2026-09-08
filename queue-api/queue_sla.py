"""
SLA de fila (backlog #46) - diferente de "tempo médio de espera"
(métrica que já existia): SLA é uma métrica binária por chamada
("foi atendida dentro de N segundos? sim/não"), agregada como
percentual - o indicador que qualquer contact center de verdade usa
como meta operacional (ex: "80% das chamadas atendidas em até 20s").

Alimentado por dois eventos AMI do Asterisk:
- AgentConnect: chamada foi atendida - campo "HoldTime" já vem com o
  tempo de espera calculado pelo próprio Asterisk.
- QueueCallerAbandon: cliente desistiu antes de ser atendido - conta
  CONTRA o SLA (não foi atendida dentro do tempo nenhum), mas ainda
  faz parte do total de chamadas oferecidas à fila.

Lógica pura aqui, sem rede - 100% testável. Reset diário com relógio
injetável, mesmo padrão de metrics.py.
"""
import time

DEFAULT_SLA_THRESHOLD_SECONDS = 20


def _day_key(timestamp: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(timestamp))


def parse_agent_connect_event(event: dict):
    """AgentConnect = chamada atendida por um agente. HoldTime = segundos que esperou na fila."""
    if event.get("Event") != "AgentConnect":
        return None
    try:
        hold_time = int(event.get("HoldTime", 0))
    except (TypeError, ValueError):
        hold_time = 0
    return {"queue": event.get("Queue", ""), "hold_time": hold_time, "outcome": "answered"}


def parse_queue_caller_abandon_event(event: dict):
    """QueueCallerAbandon = cliente desistiu antes de qualquer agente atender."""
    if event.get("Event") != "QueueCallerAbandon":
        return None
    try:
        hold_time = int(event.get("HoldTime", 0))
    except (TypeError, ValueError):
        hold_time = 0
    return {"queue": event.get("Queue", ""), "hold_time": hold_time, "outcome": "abandoned"}


class QueueSLATracker:
    """
    Acumula, por fila, quantas chamadas foram oferecidas e quantas
    foram atendidas dentro do limiar de SLA - reseta à meia-noite,
    igual à DailyMetrics.
    """

    def __init__(self, threshold_seconds: int = DEFAULT_SLA_THRESHOLD_SECONDS, clock=time.time):
        self.threshold_seconds = threshold_seconds
        self._clock = clock
        self._day = None
        self._reset_if_new_day()

    def _reset_if_new_day(self):
        today = _day_key(self._clock())
        if today != self._day:
            self._day = today
            self._queues = {}  # queue -> {"offered": int, "within_sla": int}

    def _record(self, queue: str, hold_time: int, outcome: str):
        self._reset_if_new_day()
        stats = self._queues.setdefault(queue, {"offered": 0, "within_sla": 0})
        stats["offered"] += 1
        # Abandono NUNCA conta dentro do SLA, mesmo com espera curta -
        # a chamada nunca foi atendida de fato, independente de quanto
        # tempo o cliente esperou antes de desistir.
        if outcome == "answered" and hold_time <= self.threshold_seconds:
            stats["within_sla"] += 1

    def apply_event(self, event: dict):
        answered = parse_agent_connect_event(event)
        if answered:
            self._record(answered["queue"], answered["hold_time"], "answered")
            return

        abandoned = parse_queue_caller_abandon_event(event)
        if abandoned:
            self._record(abandoned["queue"], abandoned["hold_time"], "abandoned")

    def snapshot(self) -> dict:
        """
        {fila: {offered, within_sla, sla_percent}} - fila sem nenhuma
        chamada ainda não aparece no resultado (nada pra dividir).
        """
        self._reset_if_new_day()
        result = {}
        for queue, stats in self._queues.items():
            sla_percent = round(stats["within_sla"] / stats["offered"] * 100, 1) if stats["offered"] else 0
            result[queue] = {
                "offered": stats["offered"],
                "within_sla": stats["within_sla"],
                "sla_percent": sla_percent,
            }
        return result
