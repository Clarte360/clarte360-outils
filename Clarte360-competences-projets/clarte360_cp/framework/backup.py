from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def sqlite_integrity_check(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        return str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        conn.close()


def backup_sqlite(source_db: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"competences_projets_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.sqlite3"
    src = sqlite3.connect(str(source_db)); dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()
    if sqlite_integrity_check(target) != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError("Sauvegarde SQLite invalide.")
    return target


def build_backup_manifest(db_backup: Path, objects_root: Path, output: Path) -> Path:
    objects = []
    if objects_root.exists():
        for p in sorted(x for x in objects_root.rglob("*") if x.is_file()):
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            objects.append({"path": str(p.relative_to(objects_root)), "sha256": digest, "size": p.stat().st_size})
    payload = {"database": db_backup.name, "database_sha256": hashlib.sha256(db_backup.read_bytes()).hexdigest(), "objects": objects}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def restore_database_copy(db_backup: Path, target_db: Path) -> None:
    target_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_backup, target_db)
    if sqlite_integrity_check(target_db) != "ok":
        target_db.unlink(missing_ok=True)
        raise RuntimeError("Restauration SQLite invalide.")
