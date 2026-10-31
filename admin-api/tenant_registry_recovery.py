"""Snapshot e restauração atômica do registro de tenants, sem logs de dados."""
from pathlib import Path
import stat

from conf_publisher import _restore_snapshot

MAX_REGISTRY_SNAPSHOT_BYTES = 4 * 1024 * 1024


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
    if metadata.st_size > MAX_REGISTRY_SNAPSHOT_BYTES:
        raise ValueError("registro de tenants excede limite de snapshot")
    return (target.read_bytes(), stat.S_IMODE(metadata.st_mode))


def restore_registry(path, snapshot):
    """Reverte bytes/permissão originais; ausência inicial é preservada."""
    target = Path(path)
    if target.is_symlink():
        raise ValueError("registro de tenants tornou-se link simbólico")
    if snapshot is not None:
        if (not isinstance(snapshot, tuple) or len(snapshot) != 2
                or not isinstance(snapshot[0], bytes)
                or len(snapshot[0]) > MAX_REGISTRY_SNAPSHOT_BYTES
                or type(snapshot[1]) is not int or not 0 <= snapshot[1] <= 0o777):
            raise ValueError("snapshot do registro de tenants inválido")
    _restore_snapshot(target, snapshot)
