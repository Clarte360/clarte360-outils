from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from clarte360_cp.framework.config import OBJECTS_DIR
from .models import FileObject


class IntegrityError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ObjectStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or OBJECTS_DIR)

    def path_for_hash(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
            raise ValueError("SHA-256 invalide")
        return self.root / digest[:2] / digest

    def put(self, data: bytes) -> tuple[str, Path]:
        digest = sha256_bytes(data)
        target = self.path_for_hash(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            fd, tmp = tempfile.mkstemp(prefix=".cp-", dir=str(target.parent))
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data); handle.flush(); os.fsync(handle.fileno())
                os.replace(tmp, target)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
        return digest, target

    def verify(self, digest: str) -> bool:
        path = self.path_for_hash(digest)
        if not path.exists():
            return False
        return hashlib.sha256(path.read_bytes()).hexdigest() == digest


class FileRepository:
    def __init__(self, session: Session, store: ObjectStore):
        self.session, self.store = session, store

    def register_bytes(self, data: bytes, mime: str, artifact_version_id: str | None = None) -> FileObject:
        digest, path = self.store.put(data)
        existing = self.session.scalar(select(FileObject).where(FileObject.sha256 == digest))
        if existing:
            if not self.store.verify(digest):
                raise IntegrityError("Objet existant altéré.")
            return existing
        rel = str(path.relative_to(self.store.root.parent.parent)) if self.store.root.parent.parent in path.parents else str(path)
        obj = FileObject(
            artifact_version_id=artifact_version_id, logical_path_ref=rel, mime=mime,
            size_bytes=len(data), sha256=digest,
        )
        self.session.add(obj); self.session.commit()
        return obj
