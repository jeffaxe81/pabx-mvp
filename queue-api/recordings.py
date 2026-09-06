"""
Lista os arquivos de gravação de chamadas (produzidos pelo
MixMonitor/queue monitor do Asterisk) num diretório. Lógica pura,
separada do servidor HTTP, pra dar pra testar com arquivos temporários
sem precisar subir nada.
"""
import re
import time
from pathlib import Path
from datetime import datetime

ALLOWED_EXTENSIONS = {".wav", ".gsm", ".mp3"}

# Nomes gerados pelo próprio projeto (manuais 09/14): AAAAMMDD-HHMMSS-numero-destino.wav
# Gravações vindas do monitor-type=mixmonitor da fila (manual 09) usam
# outro padrão do próprio Asterisk e não batem aqui - ficam listadas,
# só não são filtráveis por atendente/número (ver manual 21).
FILENAME_RE = re.compile(r"^(\d{8}-\d{6})-([^-]*)-([^.]+)\.\w+$")


def parse_recording_filename(filename: str):
    """
    Extrai {timestamp, caller_number, destination} do nome do arquivo,
    ou None se não bater o padrão esperado (ex: gravação gerada
    diretamente pela fila, com nome no formato do Asterisk).
    """
    match = FILENAME_RE.match(filename)
    if not match:
        return None
    timestamp, caller_number, destination = match.groups()
    return {
        "timestamp": timestamp,
        "caller_number": caller_number or None,
        "destination": destination,
    }


def list_recordings(directory, limit=50, caller_number=None, destination=None, start_date=None, end_date=None):
    """
    Retorna uma lista de dicts {filename, size_bytes, modified_at,
    caller_number, destination}, ordenada da gravação mais recente pra
    mais antiga. Filtros (todos opcionais): caller_number e
    destination fazem correspondência exata; start_date/end_date
    (formato AAAAMMDD) comparam pela data no nome do arquivo.
    Gravações cujo nome não bate no padrão esperado só aparecem
    quando nenhum filtro de atendente/número/período é usado.
    """
    path = Path(directory)
    if not path.exists():
        return []

    files = [
        f for f in path.iterdir()
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    ]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    has_filter = any([caller_number, destination, start_date, end_date])

    result = []
    for f in files:
        parsed = parse_recording_filename(f.name)

        if has_filter:
            if not parsed:
                continue  # não dá pra filtrar o que não sabemos parsear
            if caller_number and parsed["caller_number"] != caller_number:
                continue
            if destination and parsed["destination"] != destination:
                continue
            file_date = parsed["timestamp"][:8]
            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue

        stat = f.stat()
        entry = {
            "filename": f.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "caller_number": parsed["caller_number"] if parsed else None,
            "destination": parsed["destination"] if parsed else None,
        }
        result.append(entry)

        if len(result) >= limit:
            break

    return result


def safe_recording_path(directory, filename: str):
    """
    Resolve o caminho de um arquivo de gravação pedido, protegendo
    contra path traversal (ex: filename="../../etc/passwd"). Retorna
    None se o arquivo não existir ou não estiver dentro do diretório
    permitido.
    """
    base = Path(directory).resolve()
    candidate = (base / Path(filename).name).resolve()

    if base not in candidate.parents and candidate != base:
        return None
    if not str(candidate).startswith(str(base)):
        return None
    if not candidate.is_file():
        return None
    if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
        return None

    return candidate


def delete_expired_recordings(directory, retention_days: int, clock=time.time):
    """
    Apaga gravações mais antigas que retention_days. retention_days <= 0
    desabilita o expurgo (retorna sem apagar nada) - política de
    retenção é opt-in, nunca ativa "por acidente".

    Retorna a lista de nomes de arquivo apagados (útil pra log/teste).
    """
    if retention_days <= 0:
        return []

    path = Path(directory)
    if not path.exists():
        return []

    cutoff = clock() - (retention_days * 86400)
    deleted = []

    for f in path.iterdir():
        if not f.is_file() or f.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted.append(f.name)

    return deleted
