from __future__ import annotations
import json, os, secrets, hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = f"sqlite:///{(ROOT/'data'/'clarte360_emargements.db').as_posix()}"

def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def make_engine(url: str | None = None) -> Engine:
    url = url or os.getenv("DATABASE_URL") or DEFAULT_DB
    connect_args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    eng = create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)
    if url.startswith("sqlite"):
        with eng.begin() as c:
            c.exec_driver_sql("PRAGMA journal_mode=WAL")
            c.exec_driver_sql("PRAGMA foreign_keys=ON")
    return eng

SCHEMA = [
"""CREATE TABLE IF NOT EXISTS admins (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 email TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL,
 full_name TEXT,
 active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL
)""",
"""CREATE TABLE IF NOT EXISTS actions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 action_no TEXT NOT NULL UNIQUE,
 title TEXT NOT NULL,
 subtitle TEXT,
 nature TEXT NOT NULL,
 mode TEXT NOT NULL,
 client_name TEXT,
 client_type TEXT,
 group_code TEXT,
 planned_hours REAL NOT NULL DEFAULT 0,
 expected_participants INTEGER,
 status TEXT NOT NULL DEFAULT 'BROUILLON',
 admin_email TEXT,
 trainer_name TEXT,
 trainer_email TEXT,
 location TEXT,
 notes TEXT,
 source TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
)""",
"""CREATE TABLE IF NOT EXISTS participants (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 action_id INTEGER NOT NULL,
 individual_action_no TEXT,
 last_name TEXT NOT NULL,
 birth_name TEXT,
 first_name TEXT NOT NULL,
 birth_date TEXT,
 email TEXT,
 employee_id TEXT,
 company_name TEXT,
 phone TEXT,
 pin_hash TEXT,
 active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE
)""",
"""CREATE TABLE IF NOT EXISTS slots (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 action_id INTEGER NOT NULL,
 slot_date TEXT NOT NULL,
 start_time TEXT NOT NULL,
 end_time TEXT NOT NULL,
 original_start_time TEXT,
 original_end_time TEXT,
 send_offset_min INTEGER NOT NULL DEFAULT -10,
 reminder1_offset_min INTEGER NOT NULL DEFAULT 20,
 reminder2_offset_min INTEGER NOT NULL DEFAULT 120,
 close_offset_min INTEGER NOT NULL DEFAULT 1440,
 public_token TEXT UNIQUE,
 status TEXT NOT NULL DEFAULT 'PREVU',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE
)""",
"""CREATE TABLE IF NOT EXISTS signature_tokens (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 participant_id INTEGER NOT NULL,
 slot_id INTEGER NOT NULL,
 token TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL,
 expires_at TEXT,
 used_at TEXT,
 UNIQUE(participant_id, slot_id),
 FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
 FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE
)""",
"""CREATE TABLE IF NOT EXISTS signatures (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 participant_id INTEGER NOT NULL,
 slot_id INTEGER NOT NULL,
 signed_at TEXT NOT NULL,
 signature_path TEXT NOT NULL,
 signature_sha256 TEXT NOT NULL,
 signer_name TEXT NOT NULL,
 method TEXT NOT NULL,
 ip_address TEXT,
 user_agent TEXT,
 declaration_text TEXT,
 status TEXT NOT NULL DEFAULT 'VALIDE',
 UNIQUE(participant_id, slot_id),
 FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
 FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE
)""",
"""CREATE TABLE IF NOT EXISTS email_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 participant_id INTEGER NOT NULL,
 slot_id INTEGER NOT NULL,
 event_type TEXT NOT NULL,
 due_at TEXT NOT NULL,
 sent_at TEXT,
 status TEXT NOT NULL DEFAULT 'PENDING',
 attempts INTEGER NOT NULL DEFAULT 0,
 last_error TEXT,
 UNIQUE(participant_id, slot_id, event_type),
 FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
 FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE
)""",
"""CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 action_id INTEGER,
 actor TEXT,
 event_type TEXT NOT NULL,
 entity_type TEXT,
 entity_id TEXT,
 details_json TEXT,
 created_at TEXT NOT NULL
)"""
]

def init_db(engine: Engine):
    with engine.begin() as c:
        for sql in SCHEMA:
            c.execute(text(sql))

def q(engine, sql, params=None):
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql), params or {}).fetchall()]

def one(engine, sql, params=None):
    rows=q(engine,sql,params)
    return rows[0] if rows else None

def execute(engine, sql, params=None):
    with engine.begin() as c:
        r=c.execute(text(sql), params or {})
        return r.lastrowid

def audit(engine, event_type, action_id=None, actor="system", entity_type=None, entity_id=None, details=None):
    execute(engine,"""INSERT INTO audit_log(action_id,actor,event_type,entity_type,entity_id,details_json,created_at)
        VALUES(:a,:actor,:e,:et,:ei,:d,:c)""",{
        "a":action_id,"actor":actor,"e":event_type,"et":entity_type,"ei":str(entity_id) if entity_id is not None else None,
        "d":json.dumps(details or {},ensure_ascii=False,default=str),"c":utcnow_iso()})

def new_token(nbytes=24): return secrets.token_urlsafe(nbytes)
def sha256_bytes(data: bytes): return hashlib.sha256(data).hexdigest()
