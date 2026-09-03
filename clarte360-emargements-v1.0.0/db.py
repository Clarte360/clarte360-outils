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
 role TEXT NOT NULL DEFAULT 'ADMIN',
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
 trainer_id INTEGER,
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


# V2 additive schema: transferable organisation/agencies + modular quality engine.
V2_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS organizations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, legal_name TEXT, address TEXT, postal_code TEXT, city TEXT, country TEXT,
 siret TEXT, rcs TEXT, naf TEXT, vat_id TEXT, nda TEXT, website TEXT, general_email TEXT, phone TEXT, timezone TEXT NOT NULL DEFAULT 'Europe/Paris',
 privacy_contact TEXT, privacy_notice TEXT, logo_path TEXT, favicon_path TEXT, primary_color TEXT, secondary_color TEXT,
 email_from_name TEXT, email_from_address TEXT, retention_months INTEGER, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS agencies (
 id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL, name TEXT NOT NULL, address TEXT, postal_code TEXT, city TEXT, country TEXT,
 siret TEXT, nda TEXT, email TEXT, phone TEXT, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE)""",
"""CREATE TABLE IF NOT EXISTS questionnaire_templates (
 id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER, code TEXT NOT NULL, version TEXT NOT NULL, prestation_type TEXT NOT NULL, campaign_kind TEXT NOT NULL,
 title TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, UNIQUE(organization_id,code,version))""",
"""CREATE TABLE IF NOT EXISTS questionnaire_questions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, template_id INTEGER NOT NULL, question_code TEXT NOT NULL, rubric_code TEXT NOT NULL, response_type TEXT NOT NULL,
 question_text TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0, required INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
 FOREIGN KEY(template_id) REFERENCES questionnaire_templates(id) ON DELETE CASCADE)""",
"""CREATE TABLE IF NOT EXISTS quality_campaigns (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, participant_id INTEGER, trainer_id INTEGER, template_id INTEGER NOT NULL, campaign_kind TEXT NOT NULL,
 due_at TEXT NOT NULL, token TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'PENDING', sent_at TEXT, reminder1_at TEXT, reminder2_at TEXT, completed_at TEXT,
 created_at TEXT NOT NULL, UNIQUE(action_id,participant_id,trainer_id,template_id,campaign_kind),
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
 FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE SET NULL, FOREIGN KEY(template_id) REFERENCES questionnaire_templates(id))""",
"""CREATE TABLE IF NOT EXISTS quality_responses (
 id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL, question_id INTEGER NOT NULL, rubric_code TEXT NOT NULL, response_type TEXT NOT NULL,
 question_text_snapshot TEXT NOT NULL, answer_json TEXT, answered_at TEXT NOT NULL, UNIQUE(campaign_id,question_id),
 FOREIGN KEY(campaign_id) REFERENCES quality_campaigns(id) ON DELETE CASCADE, FOREIGN KEY(question_id) REFERENCES questionnaire_questions(id))""",
"""CREATE TABLE IF NOT EXISTS quality_issues (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER, campaign_id INTEGER, issue_type TEXT NOT NULL, title TEXT NOT NULL, description TEXT, status TEXT NOT NULL DEFAULT 'OUVERTE',
 owner TEXT, created_at TEXT NOT NULL, closed_at TEXT, FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE SET NULL, FOREIGN KEY(campaign_id) REFERENCES quality_campaigns(id) ON DELETE SET NULL)""",
"""CREATE TABLE IF NOT EXISTS improvement_actions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, issue_id INTEGER, action_id INTEGER, title TEXT NOT NULL, description TEXT, owner TEXT, due_at TEXT, status TEXT NOT NULL DEFAULT 'A_FAIRE',
 created_at TEXT NOT NULL, completed_at TEXT, FOREIGN KEY(issue_id) REFERENCES quality_issues(id) ON DELETE SET NULL, FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE SET NULL)"""
,
"""CREATE TABLE IF NOT EXISTS quality_email_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL, event_type TEXT NOT NULL, due_at TEXT NOT NULL,
 sent_at TEXT, status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT,
 claimed_at TEXT, claim_token TEXT, created_at TEXT NOT NULL,
 UNIQUE(campaign_id,event_type), FOREIGN KEY(campaign_id) REFERENCES quality_campaigns(id) ON DELETE CASCADE)"""
]

def init_db(engine: Engine):
    with engine.begin() as c:
        for sql in SCHEMA:
            c.execute(text(sql))
        for sql in V2_SCHEMA:
            c.execute(text(sql))
        # V1.1 additive migration: never rewrite existing evidence.
        migrations = [
            "ALTER TABLE admins ADD COLUMN role TEXT NOT NULL DEFAULT 'ADMIN'",
            "ALTER TABLE actions ADD COLUMN trainer_id INTEGER",
            "ALTER TABLE trainer_access_tokens ADD COLUMN trainer_id INTEGER",
            "ALTER TABLE slots ADD COLUMN parent_slot_id INTEGER",
            "ALTER TABLE slots ADD COLUMN slot_kind TEXT NOT NULL DEFAULT 'NORMAL'",
            "ALTER TABLE slots ADD COLUMN change_reason TEXT",
            "ALTER TABLE slots ADD COLUMN cancelled_at TEXT",
            "ALTER TABLE signatures ADD COLUMN access_method TEXT",
            "ALTER TABLE signatures ADD COLUMN signature_method TEXT NOT NULL DEFAULT 'MANUSCRITE'",
            "ALTER TABLE signatures ADD COLUMN is_late INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE signatures ADD COLUMN late_reason TEXT",
            "ALTER TABLE actions ADD COLUMN organization_id INTEGER",
            "ALTER TABLE actions ADD COLUMN agency_id INTEGER",
            "ALTER TABLE actions ADD COLUMN prestation_type TEXT NOT NULL DEFAULT 'FORMATION'",
            "ALTER TABLE actions ADD COLUMN use_attendance INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE actions ADD COLUMN use_quality_hot INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE actions ADD COLUMN use_quality_cold INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE actions ADD COLUMN use_trainer_feedback INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE actions ADD COLUMN archived_at TEXT",
            "ALTER TABLE organizations ADD COLUMN logo_path TEXT",
            "ALTER TABLE organizations ADD COLUMN favicon_path TEXT",
            "ALTER TABLE organizations ADD COLUMN primary_color TEXT",
            "ALTER TABLE organizations ADD COLUMN secondary_color TEXT",
            "ALTER TABLE organizations ADD COLUMN email_from_name TEXT",
            "ALTER TABLE organizations ADD COLUMN email_from_address TEXT",
            "ALTER TABLE organizations ADD COLUMN retention_months INTEGER",
            "ALTER TABLE email_events ADD COLUMN claimed_at TEXT",
            "ALTER TABLE email_events ADD COLUMN claim_token TEXT",
            "ALTER TABLE actions ADD COLUMN start_date TEXT",
            "ALTER TABLE actions ADD COLUMN end_date TEXT",
            "ALTER TABLE actions ADD COLUMN quality_cold_due_date TEXT",
            "ALTER TABLE quality_campaigns ADD COLUMN recipient_kind TEXT NOT NULL DEFAULT 'BENEFICIARY'",
            "ALTER TABLE quality_campaigns ADD COLUMN reminder1_due_at TEXT",
            "ALTER TABLE quality_campaigns ADD COLUMN reminder2_due_at TEXT",
        ]
        for sql in migrations:
            try: c.execute(text(sql))
            except Exception: pass
        extra = [
        """CREATE TABLE IF NOT EXISTS trainers (
          id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, email TEXT UNIQUE, phone TEXT,
          active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS attendance_status (
          id INTEGER PRIMARY KEY AUTOINCREMENT, participant_id INTEGER NOT NULL, slot_id INTEGER NOT NULL,
          status TEXT NOT NULL, reason TEXT, actor TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          UNIQUE(participant_id,slot_id), FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
          FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE)""",
        """CREATE TABLE IF NOT EXISTS trainer_countersignatures (
          id INTEGER PRIMARY KEY AUTOINCREMENT, slot_id INTEGER NOT NULL UNIQUE, trainer_name TEXT NOT NULL,
          trainer_email TEXT, signed_at TEXT NOT NULL, declaration_text TEXT NOT NULL, signature_path TEXT,
          signature_sha256 TEXT, method TEXT NOT NULL DEFAULT 'NOM_PRENOM', actor TEXT,
          FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE)""",
        """CREATE TABLE IF NOT EXISTS trainer_access_tokens (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, trainer_id INTEGER, token TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL, expires_at TEXT, active INTEGER NOT NULL DEFAULT 1,
          FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE)"""
        ]
        for sql in extra: c.execute(text(sql))
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_actions_status ON actions(status)",
            "CREATE INDEX IF NOT EXISTS ix_actions_org_agency ON actions(organization_id,agency_id)",
            "CREATE INDEX IF NOT EXISTS ix_participants_name ON participants(last_name,first_name)",
            "CREATE INDEX IF NOT EXISTS ix_email_events_due_status ON email_events(status,due_at)",
            "CREATE INDEX IF NOT EXISTS ix_quality_email_due_status ON quality_email_events(status,due_at)",
            "CREATE INDEX IF NOT EXISTS ix_quality_campaign_action ON quality_campaigns(action_id,status,campaign_kind)",
        ]
        for sql in indexes: c.execute(text(sql))

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
