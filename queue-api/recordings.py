"""
Lista os arquivos de gravação de chamadas (produzidos pelo
MixMonitor/queue monitor do Asterisk) num diretório. Lógica pura,
separada do servidor HTTP, pra dar pra testar com arquivos temporários
sem precisar subir nada.
"""
from pathlib import Path
from datetime import datetime

ALLOWED_EXTENSIONS = {".wav", ".gsm", ".mp3"}


def list_recordings(directory, limit=50):
    """
    Retorna uma lista de dicts {filename, size_bytes, modified_at},
    ordenada da gravação mais recente pra mais antiga.
    """
    path = Path(directory)
    if not path.exists():
        return []

    files = [
        f for f in path.iterdir()
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    ]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    result = []
    for f in files[:limit]:
        stat = f.stat()
        result.append({
            "filename": f.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
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
