"""Small local storage primitives, no database or external application writes."""
from __future__ import annotations
import json
import os
import stat
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def atomic_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Un lien symbolique ne peut pas remplacer une sauvegarde.")
    previous = path.stat() if path.exists() else None
    fd, temporary = tempfile.mkstemp(prefix='.pip-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            if previous:
                if hasattr(os, 'geteuid') and os.geteuid() == 0:
                    os.fchown(stream.fileno(), previous.st_uid, previous.st_gid)
                elif hasattr(os, 'geteuid') and previous.st_uid != os.geteuid():
                    raise PermissionError("Le proprietaire de la sauvegarde ne correspond pas au service.")
                os.fchmod(stream.fileno(), stat.S_IMODE(previous.st_mode)) if hasattr(os, 'fchmod') else None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, payload: Any) -> None:
    atomic_bytes(path, json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8'))


@contextmanager
def storage_lock(path: Path, timeout: float = 20.0):
    """Serialize short read/modify/write cycles. No lock breaking or force deletion."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Verrou de stockage invalide.")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    locked = False
    try:
        if os.name == 'nt':
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b'0')
        else:
            import fcntl
        deadline = time.monotonic() + timeout
        while not locked:
            try:
                if os.name == 'nt':
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except (BlockingIOError, PermissionError, OSError) as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Sauvegarde occupee par une autre session. Reessayez.") from exc
                time.sleep(0.05)
        yield
    finally:
        if locked:
            if os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
