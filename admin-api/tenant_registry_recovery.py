"""Snapshot e restauração atômica do registro de tenants, sem logs de dados."""
from pathlib import Path
import stat

from conf_publisher import _restore_snapshot


def snapshot_registry(path):
    target = Path(path)
    if target.is_symlink():
        raise ValueError("registro de tenants é link simbólico")
    if not target.exists():
        return None
    if not target.is_file():
        raise ValueError("registro de tenants não é arquivo regular")
    metadata = target.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("registro de tenants não é arquivo regular")
    return (target.read_bytes(), stat.S_IMODE(metadata.st_mode))


def restore_registry(path, snapshot):
    """Reverte bytes/permissão originais; ausência inicial é preservada."""
    target = Path(path)
    if target.is_symlink():
        raise ValueError("registro de tenants tornou-se link simbólico")
    _restore_snapshot(target, snapshot)
