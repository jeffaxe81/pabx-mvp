"""
Motivo de pausa do agente (backlog #44). Usa o mecanismo nativo do
Asterisk (Action QueuePause via AMI, campo "Reason") - não é uma
funcionalidade construída do zero, é a exposição correta de um
recurso já existente.

Lógica pura de validação/parsing/rastreamento aqui - a chamada de
rede de verdade fica isolada em ami_client.py, mesmo padrão do resto
do projeto.
"""
import re
import time
import json
from pathlib import Path

INTERFACE_RE = re.compile(r"^PJSIP/([a-zA-Z0-9-]+)$")


def validate_pause_request(data: dict):
    """
    Retorna (ok, error_message, cleaned_data). 'reason' é obrigatório
    só quando pausando (paused=True) - despausar não precisa de
    motivo nenhum.
    """
    extension = (data.get("extension") or "").strip()
    if not extension:
        return False, "ramal obrigatório", None

    paused = data.get("paused")
    if not isinstance(paused, bool):
        return False, "campo 'paused' deve ser true ou false", None

    reason = (data.get("reason") or "").strip()
    if paused and not reason:
        return False, "motivo da pausa é obrigatório", None

    return True, None, {"extension": extension, "paused": paused, "reason": reason}


def extract_extension_from_interface(interface: str):
    """'PJSIP/t1-recepcao' -> 't1-recepcao'. None se não bater o formato esperado."""
    match = INTERFACE_RE.match(interface or "")
    return match.group(1) if match else None


def parse_queue_member_pause_event(event: dict):
    """
    Extrai os dados de um evento AMI QueueMemberPause - disparado pelo
    Asterisk toda vez que um agente pausa/despausa (inclusive quando
    feito por outro caminho que não o nosso, ex: CLI do Asterisk) -
    é isso que mantém nosso estado sempre correto de verdade.
    """
    if event.get("Event") != "QueueMemberPause":
        return None

    extension = extract_extension_from_interface(event.get("Interface", ""))
    if not extension:
        return None

    return {
        "extension": extension,
        "paused": event.get("Paused") in ("1", "true", "True"),
        "reason": event.get("Reason", ""),
    }


class AgentPauseStore:
    """
    Estado atual de pausa de cada agente - em memória, atualizado via
    evento AMI. Opcionalmente grava histórico completo (backlog #57 -
    fecha a limitação documentada no manual 44 "sem relatório
    histórico de tempo em pausa por motivo") toda vez que um agente
    DESpausa - é o único momento em que a duração da pausa é conhecida
    por completo.
    """

    def __init__(self, history_store=None, clock=time.time):
        self._state = {}
        self._history_store = history_store
        self._clock = clock

    def apply_event(self, event: dict):
        parsed = parse_queue_member_pause_event(event)
        if not parsed:
            return

        extension = parsed["extension"]
        previous = self._state.get(extension)
        now = self._clock()

        # Estava pausado e agora despausou - fecha o registro de
        # histórico com a duração completa. Sem "previous", não tem
        # como saber quando a pausa começou (ex: primeiro evento
        # depois do queue-api reiniciar) - não registra, honesto sobre
        # o que não sabemos, em vez de inventar uma duração.
        if not parsed["paused"] and previous and previous["paused"] and self._history_store:
            self._history_store.append({
                "extension": extension,
                "reason": previous["reason"],
                "started_at": previous["since"],
                "ended_at": now,
                "duration_seconds": round(now - previous["since"], 1),
            })

        self._state[extension] = {
            "paused": parsed["paused"],
            "reason": parsed["reason"] if parsed["paused"] else "",
            "since": now,
        }

    def get(self, extension: str):
        return self._state.get(extension, {"paused": False, "reason": "", "since": None})

    def snapshot(self) -> dict:
        return dict(self._state)


class PauseHistoryStore:
    """Persistência do histórico de pausas completas - mesmo padrão JSONL de survey.py/reports.py."""

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


def summarize_pause_time_by_reason(records: list) -> dict:
    """Soma de segundos em pausa, agrupado por motivo - a pergunta operacional mais comum ("quanto tempo em almoço, no total?")."""
    totals = {}
    for r in records:
        reason = r.get("reason") or "sem motivo"
        totals[reason] = totals.get(reason, 0) + r.get("duration_seconds", 0)
    return {reason: round(total, 1) for reason, total in totals.items()}


def summarize_pause_time_by_extension(records: list) -> dict:
    """Soma de segundos em pausa e contagem de pausas, agrupado por ramal."""
    by_extension = {}
    for r in records:
        by_extension.setdefault(r["extension"], []).append(r)

    return {
        extension: {
            "total_seconds": round(sum(x.get("duration_seconds", 0) for x in group), 1),
            "count": len(group),
        }
        for extension, group in by_extension.items()
    }


def merge_pause_into_states(extension_states: list, pause_snapshot: dict) -> list:
    """
    Combina o snapshot automático (extension_states.py) com o estado
    de pausa de cada agente - mesmo padrão de merge_presence_into_states
    (manual 34). Cada item ganha 'pause_reason' (None quando o agente
    não está pausado).
    """
    result = []
    for state in extension_states:
        entry = dict(state)
        pause = pause_snapshot.get(state.get("exten"))
        entry["pause_reason"] = pause["reason"] if pause and pause["paused"] else None
        result.append(entry)
    return result
