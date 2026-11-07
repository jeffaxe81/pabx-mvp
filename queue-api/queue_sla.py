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
import os
import re
import stat
import time
from collections import deque
from datetime import date
from pathlib import Path

DEFAULT_SLA_THRESHOLD_SECONDS = 20
MAX_HOLD_SECONDS = 24 * 3600
MAX_SLA_DEDUPE_IDS = 10000
MAX_HISTORY_BYTES = 32 * 1024 * 1024
MAX_HISTORY_LINE_BYTES = 4096
_AMI_UNIQUEID = re.compile(r"[A-Za-z0-9._-]{1,96}$")


def _day_key(timestamp: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(timestamp))


def _hold_time_seconds(value):
    """Segundos completos de espera; sem dado confiável, None (nunca zero).

    Não usar int() em float: ele trunca -0.5 e 20.9, criando resultados
    falsos. Asterisk AMI fornece segundos inteiros como texto.
    """
    if type(value) is int:
        return value if 0 <= value <= MAX_HOLD_SECONDS else None
    if isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 9:
        parsed = int(value)
        return parsed if parsed <= MAX_HOLD_SECONDS else None
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
        if type(threshold_seconds) is not int or not 0 <= threshold_seconds <= 3600:
            raise ValueError("limiar de SLA inválido (0..3600 segundos)")
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
            self._seen_ami_call_order = deque()

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
            self._seen_ami_call_order.append(key)
            if len(self._seen_ami_call_order) > MAX_SLA_DEDUPE_IDS:
                self._seen_ami_calls.discard(self._seen_ami_call_order.popleft())

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


def _valid_history_row(record):
    """Valida os contadores antes de gravar; percentual nunca é confiado."""
    if not isinstance(record, dict):
        return None
    day, queue = record.get("date"), record.get("queue")
    offered, within = record.get("offered"), record.get("within_sla")
    if (not isinstance(day, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) is None
            or not _valid_queue_name(queue)
            or type(offered) is not int or type(within) is not int
            or not 1 <= offered <= 10_000_000
            or not 0 <= within <= offered):
        return None
    try:
        if date.fromisoformat(day).isoformat() != day:
            return None
    except ValueError:
        return None
    return {"date": day, "queue": queue, "offered": offered,
            "within_sla": within,
            "sla_percent": round(within / offered * 100, 1)}


def _unique_history_keys(pairs):
    parsed = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError("linha de histórico de SLA com chave duplicada")
        parsed[key] = value
    return parsed


def _reject_history_constant(_value):
    raise ValueError("histórico de SLA com número não finito")


def _open_history_file(path, *, append=False):
    """Abre cada pasta via openat e bloqueia symlinks/hardlinks/FIFOs.

    Um O_NOFOLLOW apenas no arquivo final não protege as pastas ancestrais.
    Os FDs ancoram o caminho; nenhum fallback inseguro é permitido.
    """
    if (not all(hasattr(os, option) for option in
                ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK", "O_CLOEXEC"))
            or os.open not in os.supports_dir_fd
            or os.mkdir not in os.supports_dir_fd):
        raise ValueError("filesystem sem suporte às garantias de segurança")
    candidate = Path(path)
    parts = candidate.parts
    if candidate.is_absolute():
        anchor, parts = "/", parts[1:]
    else:
        anchor = "."
    if not parts or any(item in ("", ".", "..") for item in parts):
        raise ValueError("caminho inseguro para histórico de SLA")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    directory = os.open(anchor, flags)
    fd = None
    try:
        for part in parts[:-1]:
            if append:
                try:
                    os.mkdir(part, 0o700, dir_fd=directory)
                except FileExistsError:
                    pass
            next_directory = os.open(part, flags, dir_fd=directory)
            os.close(directory)
            directory = next_directory
        mode = (os.O_WRONLY | os.O_APPEND | os.O_CREAT if append
                else os.O_RDONLY)
        try:
            fd = os.open(parts[-1], mode | os.O_NOFOLLOW |
                         os.O_NONBLOCK | os.O_CLOEXEC, 0o600,
                         dir_fd=directory)
        except FileNotFoundError:
            if not append:
                return None
            raise
        metadata = os.fstat(fd)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_size > MAX_HISTORY_BYTES):
            raise ValueError("histórico de SLA não é arquivo regular seguro")
        if append and stat.S_IMODE(metadata.st_mode) & 0o077:
            # Ajuste seguro de arquivos legados após verificar inode e links.
            os.fchmod(fd, 0o600)
        result, fd = fd, None
        return result
    except (OSError, NotImplementedError, TypeError) as exc:
        raise ValueError("falha ao abrir histórico de SLA com segurança") from exc
    finally:
        if fd is not None:
            os.close(fd)
        os.close(directory)


class SLAHistoryStore:
    """Histórico JSONL privado, limitado e protegido contra links."""

    def __init__(self, path):
        self.path = Path(path)

    def append(self, record: dict):
        row = _valid_history_row(record)
        if row is None:
            raise ValueError("resumo de SLA inválido")
        payload = (json.dumps(row, ensure_ascii=False, sort_keys=True) +
                   "\n").encode("utf-8")
        if len(payload) > MAX_HISTORY_LINE_BYTES:
            raise ValueError("resumo de SLA excede o limite")
        fd = _open_history_file(self.path, append=True)
        try:
            metadata = os.fstat(fd)
            if metadata.st_size + len(payload) > MAX_HISTORY_BYTES:
                raise ValueError("histórico de SLA atingiu limite de armazenamento")
            if os.write(fd, payload) != len(payload):
                raise OSError("escrita incompleta do histórico SLA")
            os.fsync(fd)
        finally:
            os.close(fd)

    def load_all(self) -> list:
        fd = _open_history_file(self.path)
        if fd is None:
            return []
        try:
            with os.fdopen(fd, "rb") as opened:
                fd = None
                content = opened.read(MAX_HISTORY_BYTES + 1)
            if len(content) > MAX_HISTORY_BYTES:
                raise ValueError("histórico de SLA excede o limite de leitura")
            text = content.decode("utf-8")
        finally:
            if fd is not None:
                os.close(fd)
        records = []
        for line in text.splitlines():
            if not line or len(line.encode("utf-8")) > MAX_HISTORY_LINE_BYTES:
                continue
            try:
                record = json.loads(line, object_pairs_hook=_unique_history_keys,
                                    parse_constant=_reject_history_constant)
            except (ValueError, TypeError):
                continue
            validated = _valid_history_row(record)
            if validated is not None:
                records.append(validated)
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
        queues = by_date.setdefault(r["date"], {})
        stats = queues.setdefault(r["queue"], {"offered": 0, "within_sla": 0})
        stats["offered"] += r["offered"]
        stats["within_sla"] += r["within_sla"]
        stats["sla_percent"] = round(
            stats["within_sla"] / stats["offered"] * 100, 1,
        )
    return by_date
