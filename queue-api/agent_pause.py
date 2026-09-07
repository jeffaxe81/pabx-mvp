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
    """Estado atual de pausa de cada agente - em memória, atualizado via evento AMI."""

    def __init__(self):
        self._state = {}

    def apply_event(self, event: dict):
        parsed = parse_queue_member_pause_event(event)
        if not parsed:
            return
        self._state[parsed["extension"]] = {
            "paused": parsed["paused"],
            "reason": parsed["reason"] if parsed["paused"] else "",
            "since": time.time(),
        }

    def get(self, extension: str):
        return self._state.get(extension, {"paused": False, "reason": "", "since": None})

    def snapshot(self) -> dict:
        return dict(self._state)


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
