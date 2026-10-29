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
import json
import re
import time
from pathlib import Path

DEFAULT_SLA_THRESHOLD_SECONDS = 20
_AMI_UNIQUEID = re.compile(r"[A-Za-z0-9._-]{1,96}$")


def _day_key(timestamp: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(timestamp))


def _hold_time_seconds(value):
    """Segundos completos de espera; sem dado confiável, None (nunca zero).

    Não usar int() em float: ele trunca -0.5 e 20.9, criando resultados
    falsos. Asterisk AMI fornece segundos inteiros como texto.
    """
    if type(value) is int:
        return value if value >= 0 else None
    if isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 9:
        return int(value)
    return None


def _valid_queue_name(queue):
    """Nunca registrar fila ausente, não-hashable ou com caracteres de controle."""
    return (isinstance(queue, str) and 1 <= len(queue) <= 96
            and queue.isprintable() and not any(ch.isspace() for ch in queue))


def parse_agent_connect_event(event: dict):
    """Não recompensar atendimento com HoldTime ausente/malformado."""
    if (not isinstance(event, dict) or event.get("Event") != "AgentConnect"
            or not _valid_queue_name(event.get("Queue"))):
        return None
    return {
        "queue": event.get("Queue", ""),
        "hold_time": _hold_time_seconds(event.get("HoldTime")),
        "outcome": "answered",
    }


def parse_queue_caller_abandon_event(event: dict):
    """Abandono conta contra o SLA, independentemente do HoldTime."""
    if (not isinstance(event, dict) or event.get("Event") != "QueueCallerAbandon"
            or not _valid_queue_name(event.get("Queue"))):
        return None
    return {
        "queue": event.get("Queue", ""),
        "hold_time": _hold_time_seconds(event.get("HoldTime")),
        "outcome": "abandoned",
    }


class QueueSLATracker:
    """
    Acumula, por fila, quantas chamadas foram oferecidas e quantas
    foram atendidas dentro do limiar de SLA - reseta à meia-noite,
    igual à DailyMetrics. Opcionalmente persiste o snapshot do dia
    ANTES de resetar (backlog #58 - fecha a limitação documentada no
    manual 46 "sem histórico") - é o único momento em que o dia
    fechou de vez e o resumo final é conhecido.
    """

    def __init__(self, threshold_seconds: int = DEFAULT_SLA_THRESHOLD_SECONDS, clock=time.time, history_store=None):
        self.threshold_seconds = threshold_seconds
        self._clock = clock
        self._history_store = history_store
        self._day = None
        self._reset_if_new_day()

    def _reset_if_new_day(self):
        today = _day_key(self._clock())
        if today != self._day:
            # self._day é None só na primeiríssima chamada (não há dia
            # anterior nenhum pra persistir) - qualquer outra virada de
            # dia salva o resumo antes de zerar.
            if self._day is not None and self._history_store:
                for queue, stats in self._queues.items():
                    if stats["offered"] == 0:
                        continue
                    self._history_store.append({
                        "date": self._day,
                        "queue": queue,
                        "offered": stats["offered"],
                        "within_sla": stats["within_sla"],
                        "sla_percent": round(stats["within_sla"] / stats["offered"] * 100, 1),
                    })
            self._day = today
            self._queues = {}  # queue -> {"offered": int, "within_sla": int}
            # Dedupe apenas dentro do dia da fila; não confundir t1 e t10.
            self._seen_ami_calls = set()

    def _record(self, queue: str, hold_time: int, outcome: str):
        if not _valid_queue_name(queue):
            return
        self._reset_if_new_day()
        stats = self._queues.setdefault(queue, {"offered": 0, "within_sla": 0})
        stats["offered"] += 1
        # Abandono NUNCA conta dentro do SLA, mesmo com espera curta -
        # a chamada nunca foi atendida de fato, independente de quanto
        # tempo o cliente esperou antes de desistir.
        if (outcome == "answered" and type(hold_time) is int
                and 0 <= hold_time <= self.threshold_seconds):
            stats["within_sla"] += 1

    def apply_event(self, event: dict):
        answered = parse_agent_connect_event(event)
        outcome = answered if answered else parse_queue_caller_abandon_event(event)
        if not outcome:
            return

        # AMI pode reenviar eventos após reconexão. Uniqueid identifica
        # a chamada; sem ele mantemos compatibilidade com eventos legados.
        # Quando fornecido, porém, deve ser válido para não falsificar
        # deduplicação com IDs incompletos ou tipos inesperados.
        raw_id = event.get("Uniqueid")
        if raw_id is not None and (
                not isinstance(raw_id, str) or not _AMI_UNIQUEID.fullmatch(raw_id)):
            return
        self._reset_if_new_day()
        key = (outcome["queue"], raw_id) if raw_id is not None else None
        if key is not None and key in self._seen_ami_calls:
            return
        self._record(outcome["queue"], outcome["hold_time"], outcome["outcome"])
        if key is not None:
            self._seen_ami_calls.add(key)

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


class SLAHistoryStore:
    """Persistência do histórico de SLA por dia/fila - mesmo padrão JSONL de survey.py/agent_pause.py."""

    def __init__(self, path):
        self.path = Path(path)

    def append(self, record: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_all(self) -> list:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records


def filter_sla_history_by_date_range(records: list, start: str = None, end: str = None) -> list:
    """
    Filtra o histórico de SLA por intervalo de datas (backlog #63 -
    fecha a limitação documentada no manual 59 "sem filtro de
    intervalo de datas"). `start`/`end` no formato "AAAA-MM-DD",
    inclusivos - mais simples que o filtro de pausa (agent_pause.py)
    porque aqui a data já vem como string pronta no registro, sem
    precisar converter timestamp.
    """
    filtered = records
    if start:
        filtered = [r for r in filtered if r["date"] >= start]
    if end:
        filtered = [r for r in filtered if r["date"] <= end]
    return filtered


def summarize_sla_history_by_date(records: list) -> dict:
    """
    {data: {fila: {offered, within_sla, sla_percent}}} - agrupa o
    histórico bruto por dia, e dentro de cada dia por fila, pra dar
    pra comparar "hoje vs. ontem vs. semana passada" olhando as datas.
    """
    by_date = {}
    for r in records:
        by_date.setdefault(r["date"], {})[r["queue"]] = {
            "offered": r["offered"],
            "within_sla": r["within_sla"],
            "sla_percent": r["sla_percent"],
        }
    return by_date
