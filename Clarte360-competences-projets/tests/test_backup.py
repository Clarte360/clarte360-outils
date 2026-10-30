from __future__ import annotations

import sqlite3
from pathlib import Path

from clarte360_cp.framework.backup import backup_sqlite, build_backup_manifest, restore_database_copy, sqlite_integrity_check
from clarte360_cp.repositories import CaseRepository
from .helpers import context


def test_backup_and_restore_integrity(Session, engine, tmp_path):
    with Session() as s:
        original = CaseRepository(s).open_or_create(context())
    source=Path(engine.url.database)
    backup=backup_sqlite(source,tmp_path/"backups")
    assert sqlite_integrity_check(backup)=="ok"
    objects = tmp_path / "objects"
    objects.mkdir()
    (objects / "synthetic.txt").write_text("synthetic test object", encoding="utf-8")
    manifest=build_backup_manifest(backup,objects,tmp_path/"manifest.json")
    assert manifest.exists()
    restored=tmp_path/"restore"/"cp.sqlite3"
    restore_database_copy(backup,restored)
    assert sqlite_integrity_check(restored)=="ok"
    with sqlite3.connect(restored) as restored_db:
        restored_case = restored_db.execute(
            "SELECT case_code FROM cases WHERE case_id = ?", (original.case_id,)
        ).fetchone()
    assert restored_case == (original.case_code,)
