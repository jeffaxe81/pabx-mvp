"""
Presença corporativa avançada (backlog #29): cada ramal pode definir
manualmente um estado (ausente, em reunião, férias) que sobrepõe o
estado automático do BLF (livre/tocando/ocupado, já capturado via
AMI ExtensionStatus em extension_states.py). Enquanto não houver
override manual, o estado automático continua valendo normalmente.

Lógica pura, sem rede - 100% testável. Persistido em JSON simples
(mesmo padrão de extensions_store.json) pra sobreviver a um restart
do queue-api - diferente de crachá de presença efêmero, "estou de
férias" não deveria resetar sozinho.
"""
import json
import os
import tempfile
import time
from pathlib import Path

PRESENCE_STATES = {"disponivel", "ausente", "reuniao", "ferias"}


def validate_presence_input(data: dict):
    """Retorna (ok, error_message, cleaned_data)."""
    status = (data.get("status") or "").strip()
    if status not in PRESENCE_STATES:
        return False, f"status inválido - use um de: {', '.join(sorted(PRESENCE_STATES))}", None

    note = (data.get("note") or "").strip()
    return True, None, {"status": status, "note": note}


def load_presence(path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_presence(path, data: dict):
    """Evita corromper o mapa de presença em escritas interrompidas."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=f".{destination.name}.", delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def set_presence(path, extension: str, status: str, note: str = ""):
    data = load_presence(path)
    data[extension] = {"status": status, "note": note, "updated_at": time.time()}
    save_presence(path, data)
    return data[extension]


def clear_presence(path, extension: str) -> bool:
    """
    Remove o override manual - o ramal volta a mostrar só o estado
    automático do BLF (equivalente a "disponível", mas sem manter um
    registro de override desnecessário).
    """
    data = load_presence(path)
    if extension not in data:
        return False
    del data[extension]
    save_presence(path, data)
    return True


def merge_presence_into_states(extension_states: list, presence_map: dict) -> list:
    """
    Combina o snapshot automático (extension_states.py) com os
    overrides manuais. Cada item ganha 'manual_status'/'manual_note'
    (None quando não há override) - a interface decide como priorizar
    a exibição.
    """
    result = []
    for state in extension_states:
        entry = dict(state)
        override = presence_map.get(state.get("exten"))
        if override:
            entry["manual_status"] = override["status"]
            entry["manual_note"] = override.get("note", "")
        else:
            entry["manual_status"] = None
            entry["manual_note"] = None
        result.append(entry)
    return result
