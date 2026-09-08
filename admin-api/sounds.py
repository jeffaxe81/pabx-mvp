"""
Listagem de áudios customizados gerados/gravados (backlog #53) -
completa o manual 48 (TTS): gerava áudio, mas não tinha como ver o
que já existia sem entrar no servidor de arquivos.
"""
from pathlib import Path


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
