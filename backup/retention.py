"""
Retenção de arquivos de backup (backlog #33) - mesma lógica já usada
pras gravações de chamada (queue-api/recordings.py): apaga arquivo
mais antigo que N dias, com retention_days <= 0 desabilitando por
completo (nunca apaga nada sozinho, opt-in de propósito).

Lógica pura, sem rede - 100% testável.
"""
import sys
import time
from pathlib import Path


def delete_old_backups(directory, retention_days: int, clock=time.time):
    """Retorna a lista de nomes de arquivo apagados (útil pra log/teste)."""
    if retention_days <= 0:
        return []

    path = Path(directory)
    if not path.exists():
        return []

    cutoff = clock() - (retention_days * 86400)
    deleted = []

    for f in path.iterdir():
        if not f.is_file() or not f.name.endswith(".tar.gz"):
            continue
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted.append(f.name)

    return deleted


def list_backups(directory):
    """Lista os backups existentes, mais recente primeiro - usado só pra inspeção/log."""
    path = Path(directory)
    if not path.exists():
        return []

    files = [f for f in path.iterdir() if f.is_file() and f.name.endswith(".tar.gz")]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return [f.name for f in files]


if __name__ == "__main__":
    backup_dir = sys.argv[1] if len(sys.argv) > 1 else "/backups"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    deleted = delete_old_backups(backup_dir, days)
    if deleted:
        print(f"[retenção backup] apagados ({len(deleted)}): {deleted}")
    else:
        print("[retenção backup] nada pra apagar (ou retenção desabilitada)")
