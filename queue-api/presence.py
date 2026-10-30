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
import math
import os
import re
import stat
import tempfile
import time
from pathlib import Path

PRESENCE_STATES = {"disponivel", "ausente", "reuniao", "ferias"}
MAX_PRESENCE_BYTES = 1024 * 1024
_EXTENSION_RE = re.compile(r"^t[1-9][0-9]*-[A-Za-z0-9_-]{1,80}$")


def validate_presence_input(data: dict):
    """Retorna (ok, error_message, cleaned_data)."""
    if not isinstance(data, dict):
        return False, "presenca deve ser objeto JSON", None
    status = data.get("status", "")
    if not isinstance(status, str):
        return False, "status invalido", None
    status = status.strip()
    if status not in PRESENCE_STATES:
        return False, f"status inválido - use um de: {', '.join(sorted(PRESENCE_STATES))}", None

    note = data.get("note", "")
    if not isinstance(note, str) or len(note) > 256:
        return False, "nota invalida ou longa demais", None
    note = note.strip()
    return True, None, {"status": status, "note": note}


def load_presence(path) -> dict:
    # Nunca seguir um symlink apontado pelo catálogo nem carregar um
    # JSON ilimitado; corrupção deve ser visível, não sobrescrita.
    try:
        fd = os.open(Path(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                     | getattr(os, "O_NONBLOCK", 0))
    except FileNotFoundError:
        return {}
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_PRESENCE_BYTES:
            raise ValueError("catálogo de presença inseguro ou excessivo")
        with os.fdopen(fd, "rb") as source:
            fd = -1
            raw = source.read(MAX_PRESENCE_BYTES + 1)
    finally:
        if fd >= 0:
            os.close(fd)
    if len(raw) > MAX_PRESENCE_BYTES:
        raise ValueError("catálogo de presença excede o limite")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("catálogo de presença não é objeto")
    for extension, entry in data.items():
        if (not isinstance(extension, str) or
                _EXTENSION_RE.fullmatch(extension) is None or
                not isinstance(entry, dict) or
                entry.get("status") not in PRESENCE_STATES or
                not isinstance(entry.get("note", ""), str) or
                len(entry.get("note", "")) > 256 or
                type(entry.get("updated_at")) not in (int, float) or
                not math.isfinite(entry["updated_at"])):
            raise ValueError("registro de presença inválido")
    return data


def save_presence(path, data: dict):
    """Evita corromper o mapa de presença em escritas interrompidas."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, indent=2, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_PRESENCE_BYTES:
        raise ValueError("catálogo de presença excede o limite")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=f".{destination.name}.", delete=False,
        ) as handle:
            temporary = handle.name
            handle.write(encoded)
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
