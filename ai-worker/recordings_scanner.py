"""
Lista gravações que ainda não foram processadas pelo pipeline de IA.
Lógica pura (recebe o diretório e o conjunto de nomes já processados,
devolve a lista de pendentes) - a decisão de QUAL processar primeiro
(mais antiga primeiro) e a persistência ficam fora daqui.
"""
from pathlib import Path

SUPPORTED_EXTENSIONS = {".wav", ".gsm", ".mp3"}


def list_unprocessed_recordings(directory, already_processed: set) -> list:
    """
    Retorna os nomes de arquivo (não caminhos completos) das
    gravações no diretório que ainda não estão em `already_processed`,
    ordenadas da mais antiga pra mais nova (processa em ordem de
    chegada, não aleatório).
    """
    path = Path(directory)
    if not path.exists():
        return []

    files = [
        f for f in path.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS and f.name not in already_processed
    ]
    files.sort(key=lambda f: f.stat().st_mtime)
    return [f.name for f in files]
