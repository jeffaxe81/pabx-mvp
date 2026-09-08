"""
Listagem de áudios customizados gerados/gravados (backlog #53) -
completa o manual 48 (TTS): gerava áudio, mas não tinha como ver o
que já existia sem entrar no servidor de arquivos.
"""
import re
from pathlib import Path

# Só letras minúsculas/números/hífen + ".wav" - rejeita qualquer
# tentativa de path traversal (../, /, caracteres especiais) antes
# mesmo de tocar no sistema de arquivos (backlog #60, reprodução de
# áudio pela interface).
SAFE_FILENAME_RE = re.compile(r"^[a-z0-9-]{1,60}\.wav$")


def is_safe_sound_filename(filename: str) -> bool:
    """
    Valida que um nome de arquivo é seguro pra servir como resposta
    HTTP - sem isso, alguém poderia pedir "../../etc/passwd" (ou
    qualquer outro arquivo do sistema) via
    GET /api/sounds/<filename escolhido pelo cliente>.
    """
    return bool(SAFE_FILENAME_RE.match(filename or ""))


def list_sound_files(directory) -> list:
    """
    Lista os arquivos .wav de um diretório, com metadados básicos, do
    mais recente pro mais antigo (o mais provável de interessar quem
    acabou de gerar um áudio novo). Diretório inexistente = lista
    vazia, não erro (comportamento defensivo, mesmo padrão de
    load_tenants/load_presence).
    """
    directory = Path(directory)
    if not directory.exists():
        return []

    entries = []
    for path in directory.glob("*.wav"):
        stat = path.stat()
        entries.append({
            "filename": path.name,
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        })

    entries.sort(key=lambda e: e["modified_at"], reverse=True)
    return entries
