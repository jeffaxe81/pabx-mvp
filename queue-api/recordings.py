"""
Lista os arquivos de gravação de chamadas (produzidos pelo
MixMonitor/queue monitor do Asterisk) num diretório. Lógica pura,
separada do servidor HTTP, pra dar pra testar com arquivos temporários
sem precisar subir nada.
"""
import os
import re
import stat
import time
from pathlib import Path
from datetime import datetime

ALLOWED_EXTENSIONS = {".wav", ".gsm", ".mp3"}

# Nomes gerados pelo próprio projeto (manuais 09/14): AAAAMMDD-HHMMSS-numero-destino.wav
# Gravações vindas do monitor-type=mixmonitor da fila (manual 09) usam
# outro padrão do próprio Asterisk e não batem aqui - ficam listadas,
# só não são filtráveis por atendente/número (ver manual 21).
FILENAME_RE = re.compile(r"^(\d{8}-\d{6})-([^-]*)-([^.]+)\.\w+$")
_OPEN_SUPPORTS_DIR_FD = os.open in getattr(os, "supports_dir_fd", ())


def _recording_directory_fd(directory):
    """Ancora cada componente da pasta sem seguir links simbólicos.

    Abertura relativa por FD impede que a troca de um ancestral
    redirecione a listagem ou o download para outro diretório.
    """
    if not _OPEN_SUPPORTS_DIR_FD or not all(
        hasattr(os, attr) for attr in ("O_DIRECTORY", "O_NOFOLLOW")
    ):
        return None
    current_fd = None
    try:
        path = Path(directory)
        components = path.parts[1:] if path.is_absolute() else path.parts
        if any(part in {"", ".", ".."} for part in components):
            return None
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        current_fd = os.open("/" if path.is_absolute() else ".", flags)
        for part in components:
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        opened_fd, current_fd = current_fd, None
        return opened_fd
    except (OSError, TypeError, ValueError, NotImplementedError):
        return None
    finally:
        if current_fd is not None:
            os.close(current_fd)



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
    if not isinstance(limit, int) or limit <= 0:
        return []
    directory_fd = _recording_directory_fd(directory)
    if directory_fd is None:
        return []

    has_filter = any([caller_number, destination, start_date, end_date])
    candidates = []
    try:
        # scandir(fd) usa o diretório já aberto. stat(..., follow_symlinks=False)
        # não segue um link inserido depois da enumeração.
        with os.scandir(directory_fd) as entries:
            for entry in entries:
                name = entry.name
                if (not isinstance(name, str) or len(name) > 240
                        or "/" in name or "\\" in name
                        or any(ord(char) < 32 or ord(char) == 127 for char in name)
                        or Path(name).suffix.lower() not in ALLOWED_EXTENSIONS):
                    continue
                parsed = parse_recording_filename(name)
                if has_filter:
                    if not parsed:
                        continue
                    if caller_number and parsed["caller_number"] != caller_number:
                        continue
                    if destination and parsed["destination"] != destination:
                        continue
                    file_date = parsed["timestamp"][:8]
                    if start_date and file_date < start_date:
                        continue
                    if end_date and file_date > end_date:
                        continue
                try:
                    info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                except (OSError, ValueError):
                    # Renomeado/removido entre scandir e fstatat: não publicar.
                    continue
                if not stat.S_ISREG(info.st_mode):
                    continue
                candidates.append((info.st_mtime, name, info, parsed))
    except (OSError, TypeError, ValueError, NotImplementedError):
        return []
    finally:
        os.close(directory_fd)

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "filename": name,
            "size_bytes": info.st_size,
            "modified_at": datetime.fromtimestamp(info.st_mtime).isoformat(timespec="seconds"),
            "caller_number": parsed["caller_number"] if parsed else None,
            "destination": parsed["destination"] if parsed else None,
        }
        for _, name, info, parsed in candidates[:limit]
    ]


def safe_recording_path(directory, filename: str):
    """
    Resolve o caminho de um arquivo de gravação pedido, protegendo
    contra path traversal (ex: filename="../../etc/passwd"). Retorna
    None se o arquivo não existir ou não estiver dentro do diretório
    permitido.
    """
    # Não transformar um caminho arbitrário no seu basename: rejeite
    # completamente componentes de diretório enviados pelo cliente.
    if not isinstance(filename, str) or not filename or "/" in filename or "\\" in filename:
        return None
    base = Path(directory).resolve()
    raw_candidate = base / filename
    if raw_candidate.is_symlink():
        return None
    candidate = raw_candidate.resolve()

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
        if f.is_symlink() or not f.is_file() or f.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted.append(f.name)

    return deleted


def open_recording_file(directory, filename):
    """Abre um audio regular sem seguir symlinks, mesmo em troca concorrente.

    O descritor da pasta ancora o openat() e o descritor retornado
    ancora o conteudo enviado pelo HTTP. Destinado ao host Linux/Docker.
    Falha fechado para caminhos inseguros, links e arquivos especiais.
    """
    if (
        not isinstance(filename, str) or filename in {"", ".", ".."}
        or "/" in filename or "\\" in filename
        or Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
    ):
        return None

    directory_fd = None
    file_fd = None
    try:
        directory_fd = _recording_directory_fd(directory)
        if directory_fd is None:
            return None
        file_fd = os.open(
            filename,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory_fd,
        )
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            return None
        opened = os.fdopen(file_fd, "rb")
        file_fd = None  # O file object passa a possuir o descritor.
        return opened
    except (OSError, ValueError, TypeError):
        return None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)
