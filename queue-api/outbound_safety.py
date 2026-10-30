"""Shared-volume outbound claim safety for the AXE PABX queue API.

Linux flock coordinates processes pointing at the *same inode* on a
flock-capable shared filesystem. Never use separate per-pod volumes.
"""
import fcntl
import json
import os
import stat
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

_LOCAL_LOCK = threading.RLock()


@contextmanager
def outbound_lock(path, wait_seconds=10):
    """Thread and cross-process exclusion; fail closed if unavailable."""
    lock_path = Path(str(path) + ".lock")
    with _LOCAL_LOCK:
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(lock_path, flags, 0o600)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) & 0o077):
                raise PermissionError("unsafe outbound lock")
            deadline = time.monotonic() + wait_seconds
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("outbound lock busy")
                    time.sleep(0.03)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def atomic_write_json(path, records):
    """Durably replace one JSON snapshot, leaving old state on write error.

    Call under outbound_lock whenever the file is shared between
    processes. Readers see either the old or the new complete JSON.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + target.name + ".", dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(records, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
        # fsync directory to persist rename across power loss.
        parent = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def audit_event(path, entry):
    """Append a durable audit event. Caller holds outbound_lock(path)."""
    audit_path = Path(str(path) + ".audit.jsonl")
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(audit_path, flags, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise PermissionError("unsafe audit log")
        if not isinstance(entry, dict):
            raise ValueError("registro de auditoria inválido")
        data = (json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n").encode()
        if len(data) > 65536:
            raise ValueError("registro de auditoria excessivo")
        if os.write(fd, data) != len(data):
            raise OSError("incomplete audit append")
        os.fsync(fd)
    finally:
        os.close(fd)
