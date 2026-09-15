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
 UNIQUE(campaign_id,event_type), FOREIGN KEY(campaign_id) REFERENCES quality_campaigns(id) ON DELETE CASCADE)""",
"""CREATE TABLE IF NOT EXISTS trainer_reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, trainer_id INTEGER NOT NULL, report_type TEXT NOT NULL,
 subject TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'NOUVEAU', quality_relevant INTEGER NOT NULL DEFAULT 0,
 attachment_path TEXT, attachment_name TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE CASCADE)""",
"""CREATE TABLE IF NOT EXISTS trainer_password_resets (
 id INTEGER PRIMARY KEY AUTOINCREMENT, trainer_id INTEGER NOT NULL, token TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, used_at TEXT, created_at TEXT NOT NULL,
 FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE CASCADE)""",
"""CREATE TABLE IF NOT EXISTS beneficiaries (
 id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, last_name TEXT NOT NULL, first_name TEXT NOT NULL, birth_date TEXT NOT NULL,
 birth_name TEXT, current_email TEXT, phone TEXT, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS beneficiary_portal_accounts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, beneficiary_id INTEGER NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE, password_hash TEXT, active INTEGER NOT NULL DEFAULT 1,
 email_verified_at TEXT, invite_token TEXT UNIQUE, invite_expires_at TEXT, invited_at TEXT, last_login_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(beneficiary_id) REFERENCES beneficiaries(id) ON DELETE CASCADE)""",
"""CREATE TABLE IF NOT EXISTS beneficiary_password_resets (
 id INTEGER PRIMARY KEY AUTOINCREMENT, beneficiary_id INTEGER NOT NULL, token TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, used_at TEXT, created_at TEXT NOT NULL,
 FOREIGN KEY(beneficiary_id) REFERENCES beneficiaries(id) ON DELETE CASCADE)""",
"""CREATE TABLE IF NOT EXISTS stored_files (
 id INTEGER PRIMARY KEY AUTOINCREMENT, sha256 TEXT NOT NULL UNIQUE, storage_path TEXT NOT NULL, size_bytes INTEGER NOT NULL, mime_type TEXT, extension TEXT,
 created_at TEXT NOT NULL, last_verified_at TEXT)""",
"""CREATE TABLE IF NOT EXISTS document_references (
 id INTEGER PRIMARY KEY AUTOINCREMENT, stored_file_id INTEGER NOT NULL, action_id INTEGER, beneficiary_id INTEGER, participant_id INTEGER,
 category TEXT NOT NULL, display_name TEXT NOT NULL, audience TEXT NOT NULL DEFAULT 'ACTION_BENEFICIARIES', visible_to_beneficiary INTEGER NOT NULL DEFAULT 1,
 uploaded_by TEXT, created_at TEXT NOT NULL, deleted_at TEXT,
 FOREIGN KEY(stored_file_id) REFERENCES stored_files(id), FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE,
 FOREIGN KEY(beneficiary_id) REFERENCES beneficiaries(id) ON DELETE CASCADE, FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE)"""
]

I9A_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS auth_sessions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT NOT NULL UNIQUE, subject_type TEXT NOT NULL, subject_ref TEXT NOT NULL,
 created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT, ip_hash TEXT, user_agent_hash TEXT
)"""
]

I9B_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS communication_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, participant_id INTEGER, trainer_id INTEGER, slot_id INTEGER,
 communication_type TEXT NOT NULL, recipient_email TEXT, trigger_mode TEXT NOT NULL DEFAULT 'AUTO', status TEXT NOT NULL DEFAULT 'A_ENVOYER',
 due_at TEXT, sent_at TEXT, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, metadata_json TEXT, idempotency_key TEXT UNIQUE,
 claimed_at TEXT, claim_token TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE SET NULL,
 FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE SET NULL, FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE
)"""
]

I9D_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS tool_catalog (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tool_code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'OUTIL',
 base_url TEXT, tool_version TEXT, active INTEGER NOT NULL DEFAULT 1, allowed_publics_json TEXT, compatible_prestations_json TEXT,
 prescription_allowed INTEGER NOT NULL DEFAULT 1, launch_type TEXT NOT NULL DEFAULT 'HUB_REDIRECT', input_contract_json TEXT,
 output_contract_json TEXT, access_validity_hours INTEGER NOT NULL DEFAULT 168, rgpd_rules_json TEXT, connector_code TEXT,
 connector_status TEXT NOT NULL DEFAULT 'NOT_CONFIGURED', metadata_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
)""",
"""CREATE TABLE IF NOT EXISTS tool_prescriptions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, prescription_id TEXT NOT NULL UNIQUE, tool_id INTEGER NOT NULL, tool_code TEXT NOT NULL, tool_version TEXT,
 beneficiary_id INTEGER NOT NULL, action_id INTEGER NOT NULL, participant_id INTEGER, prescriber_type TEXT NOT NULL, prescriber_id TEXT, prescriber_role TEXT NOT NULL,
 created_at TEXT NOT NULL, due_at TEXT, expires_at TEXT, status TEXT NOT NULL DEFAULT 'A_FAIRE', first_viewed_at TEXT, started_at TEXT, completed_at TEXT,
 reviewed_at TEXT, cancelled_at TEXT, result_refs_json TEXT, metadata_json TEXT, updated_at TEXT NOT NULL,
 FOREIGN KEY(tool_id) REFERENCES tool_catalog(id), FOREIGN KEY(beneficiary_id) REFERENCES beneficiaries(id) ON DELETE CASCADE,
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE SET NULL
)""",
"""CREATE TABLE IF NOT EXISTS prescription_access_tokens (
 id INTEGER PRIMARY KEY AUTOINCREMENT, prescription_id TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 used_at TEXT, revoked_at TEXT, created_by TEXT, FOREIGN KEY(prescription_id) REFERENCES tool_prescriptions(prescription_id) ON DELETE CASCADE
)""",
"""CREATE TABLE IF NOT EXISTS prescription_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, prescription_id TEXT NOT NULL, event_type TEXT NOT NULL, old_status TEXT, new_status TEXT, actor TEXT NOT NULL,
 details_json TEXT, event_id TEXT UNIQUE, created_at TEXT NOT NULL, FOREIGN KEY(prescription_id) REFERENCES tool_prescriptions(prescription_id) ON DELETE CASCADE
)"""
]

I9E_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS connector_cursors (
 connector_code TEXT PRIMARY KEY, source_ref TEXT, byte_offset INTEGER NOT NULL DEFAULT 0, last_event_at TEXT, last_error TEXT, updated_at TEXT NOT NULL
)"""
]

I9F_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS study_export_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, purpose TEXT NOT NULL, format TEXT NOT NULL, filters_json TEXT, schema_version TEXT NOT NULL,
 record_count INTEGER NOT NULL DEFAULT 0, exported_at TEXT NOT NULL
)"""
]

I9G_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS crm_contacts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, source TEXT NOT NULL DEFAULT 'MANUEL', source_ref TEXT,
 first_name TEXT NOT NULL, last_name TEXT NOT NULL, email TEXT NOT NULL, email_verified_at TEXT, phone TEXT, job_title TEXT, company TEXT,
 interests_json TEXT, research_consent_at TEXT, marketing_consent INTEGER NOT NULL DEFAULT 0, marketing_consent_at TEXT, marketing_revoked_at TEXT,
 rgpd_notice_version TEXT, status TEXT NOT NULL DEFAULT 'NOUVEAU', beneficiary_id INTEGER, converted_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(beneficiary_id) REFERENCES beneficiaries(id) ON DELETE SET NULL
)""",
"""CREATE TABLE IF NOT EXISTS crm_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id INTEGER NOT NULL, event_type TEXT NOT NULL, actor TEXT NOT NULL, details_json TEXT, created_at TEXT NOT NULL,
 FOREIGN KEY(contact_id) REFERENCES crm_contacts(id) ON DELETE CASCADE
)""",
"""CREATE TABLE IF NOT EXISTS contractualization_cases (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, beneficiary_id INTEGER NOT NULL, participant_id INTEGER, no_clar TEXT,
 prestation_type TEXT, contract_type TEXT, aps_ref TEXT, aps_payload_json TEXT, status TEXT NOT NULL DEFAULT 'A_PREPARER', external_ref TEXT,
 pdf_ref TEXT, json_ref TEXT, financing_refs_json TEXT, warnings_json TEXT, context_payload_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(beneficiary_id) REFERENCES beneficiaries(id) ON DELETE CASCADE,
 FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE SET NULL
)""",
"""CREATE TABLE IF NOT EXISTS contractualization_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL, event_type TEXT NOT NULL, old_status TEXT, new_status TEXT, actor TEXT NOT NULL,
 details_json TEXT, created_at TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES contractualization_cases(id) ON DELETE CASCADE
)"""
]


def init_db(engine: Engine):
    with engine.begin() as c:
        for sql in SCHEMA:
            c.execute(text(sql))
        for sql in V2_SCHEMA:
            c.execute(text(sql))
        for sql in I9A_SCHEMA:
            c.execute(text(sql))
        for sql in I9B_SCHEMA:
            c.execute(text(sql))
        for sql in I9D_SCHEMA:
            c.execute(text(sql))
        for sql in I9E_SCHEMA:
            c.execute(text(sql))
        for sql in I9F_SCHEMA:
            c.execute(text(sql))
        for sql in I9G_SCHEMA:
            c.execute(text(sql))
        # V1.1 additive migration: never rewrite existing evidence.
        migrations = [
            "ALTER TABLE admins ADD COLUMN role TEXT NOT NULL DEFAULT 'ADMIN'",
            "ALTER TABLE actions ADD COLUMN trainer_id INTEGER",
            "ALTER TABLE actions ADD COLUMN delivery_mode TEXT",
            "ALTER TABLE trainer_access_tokens ADD COLUMN trainer_id INTEGER",
            "ALTER TABLE trainers ADD COLUMN password_hash TEXT",
            "ALTER TABLE trainers ADD COLUMN invite_token TEXT",
            "ALTER TABLE trainers ADD COLUMN invite_expires_at TEXT",
            "ALTER TABLE trainers ADD COLUMN invited_at TEXT",
            "ALTER TABLE trainers ADD COLUMN last_login_at TEXT",
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
            "ALTER TABLE quality_campaigns ADD COLUMN manual_reminder_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE quality_campaigns ADD COLUMN last_manual_reminder_at TEXT",
            "ALTER TABLE quality_campaigns ADD COLUMN last_manual_reminder_by TEXT",
            "ALTER TABLE participants ADD COLUMN pin_recovery_cipher TEXT",
            "ALTER TABLE trainers ADD COLUMN reset_requested_at TEXT",
            "ALTER TABLE trainers ADD COLUMN can_upload_documents INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE trainers ADD COLUMN microsoft_email TEXT",
            "ALTER TABLE trainers ADD COLUMN entra_user_id TEXT",
            "ALTER TABLE trainers ADD COLUMN entra_status TEXT NOT NULL DEFAULT 'UNCHECKED'",
            "ALTER TABLE trainers ADD COLUMN entra_last_verified_at TEXT",
            "ALTER TABLE trainers ADD COLUMN entra_creation_requested_at TEXT",
            "ALTER TABLE trainers ADD COLUMN entra_creation_requested_by TEXT",
            "ALTER TABLE participants ADD COLUMN beneficiary_id INTEGER",
            "ALTER TABLE beneficiary_portal_accounts ADD COLUMN pending_email TEXT",
            "ALTER TABLE actions ADD COLUMN client_admin_email TEXT",
            "ALTER TABLE actions ADD COLUMN client_training_email TEXT",
            "ALTER TABLE actions ADD COLUMN client_quality_email TEXT",
            "ALTER TABLE actions ADD COLUMN client_billing_email TEXT",
            "ALTER TABLE actions ADD COLUMN client_other_email TEXT",
            "ALTER TABLE actions ADD COLUMN final_bundle_due_at TEXT",
            "ALTER TABLE actions ADD COLUMN final_bundle_generated_at TEXT",
            "ALTER TABLE actions ADD COLUMN final_bundle_path TEXT",
            "ALTER TABLE actions ADD COLUMN portal_expires_at TEXT",
            "ALTER TABLE actions ADD COLUMN portal_warning_sent_at TEXT",
            "ALTER TABLE actions ADD COLUMN quality_contact_name TEXT",
            "ALTER TABLE actions ADD COLUMN training_contact_name TEXT",
            "ALTER TABLE actions ADD COLUMN training_contact_phone TEXT",
            "ALTER TABLE actions ADD COLUMN transmit_final_bundle INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE actions ADD COLUMN send_final_to_quality INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE actions ADD COLUMN send_final_to_training INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE actions ADD COLUMN final_other_first_name TEXT",
            "ALTER TABLE actions ADD COLUMN final_other_last_name TEXT",
            "ALTER TABLE actions ADD COLUMN final_other_email TEXT",
            "ALTER TABLE action_trainers ADD COLUMN can_manage_planning INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE slot_trainers ADD COLUMN can_manage_planning INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE action_trainers ADD COLUMN can_prescribe_tools INTEGER NOT NULL DEFAULT 0",
        ]
        for sql in migrations:
            try: c.execute(text(sql))
            except Exception: pass
        extra = [
        """CREATE TABLE IF NOT EXISTS trainers (
          id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, email TEXT UNIQUE, phone TEXT,
          password_hash TEXT, invite_token TEXT, invite_expires_at TEXT, invited_at TEXT, last_login_at TEXT, reset_requested_at TEXT,
          microsoft_email TEXT, entra_user_id TEXT, entra_status TEXT NOT NULL DEFAULT 'UNCHECKED', entra_last_verified_at TEXT,
          entra_creation_requested_at TEXT, entra_creation_requested_by TEXT,
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
        """CREATE TABLE IF NOT EXISTS client_transmissions (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, transmission_type TEXT NOT NULL, recipient_email TEXT NOT NULL,
          document_name TEXT, campaign_id INTEGER, status TEXT NOT NULL DEFAULT 'PENDING', sent_at TEXT, last_error TEXT, created_at TEXT NOT NULL,
          claimed_at TEXT, claim_token TEXT, attempts INTEGER NOT NULL DEFAULT 0,
          FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(campaign_id) REFERENCES quality_campaigns(id) ON DELETE SET NULL)""",
        """CREATE TABLE IF NOT EXISTS trainer_access_tokens (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, trainer_id INTEGER, token TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL, expires_at TEXT, active INTEGER NOT NULL DEFAULT 1,
          FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE)"""
        ]
        for sql in extra: c.execute(text(sql))

        # V3 I1 additive foundation. These structures coexist with the V2 columns
        # during the transition so existing actions and proofs remain readable.
        v3_i1_schema = [
        """CREATE TABLE IF NOT EXISTS action_trainers (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, trainer_id INTEGER NOT NULL,
          role TEXT NOT NULL DEFAULT 'INTERVENANT', is_referent INTEGER NOT NULL DEFAULT 0,
          start_date TEXT, end_date TEXT, can_manage_planning INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          UNIQUE(action_id,trainer_id), FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE,
          FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE CASCADE)""",
        """CREATE TABLE IF NOT EXISTS slot_trainers (
          id INTEGER PRIMARY KEY AUTOINCREMENT, slot_id INTEGER NOT NULL, trainer_id INTEGER NOT NULL,
          role TEXT NOT NULL DEFAULT 'PRINCIPAL', assignment_status TEXT NOT NULL DEFAULT 'ACTIVE',
          replaced_assignment_id INTEGER, reason TEXT, created_by TEXT, can_manage_planning INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(slot_id,trainer_id),
          FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE, FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE CASCADE,
          FOREIGN KEY(replaced_assignment_id) REFERENCES slot_trainers(id) ON DELETE SET NULL)""",
        """CREATE TABLE IF NOT EXISTS trainer_assignment_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT, scope_type TEXT NOT NULL, action_id INTEGER NOT NULL, slot_id INTEGER, trainer_id INTEGER,
          event_type TEXT NOT NULL, old_role TEXT, new_role TEXT, old_status TEXT, new_status TEXT, reason TEXT, actor TEXT,
          created_at TEXT NOT NULL, migration_key TEXT UNIQUE, FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE,
          FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE, FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE SET NULL)""",
        """CREATE TABLE IF NOT EXISTS action_modules (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, module_code TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0,
          enabled_at TEXT, enabled_by TEXT, effective_from TEXT, config_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          UNIQUE(action_id,module_code), FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE)"""
        ]
        for sql in v3_i1_schema: c.execute(text(sql))
        # I4 permissions must also be added to production databases where the I1 tables already exist.
        for sql in [
            "ALTER TABLE action_trainers ADD COLUMN can_manage_planning INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE slot_trainers ADD COLUMN can_manage_planning INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE action_trainers ADD COLUMN can_prescribe_tools INTEGER NOT NULL DEFAULT 0",
        ]:
            try: c.execute(text(sql))
            except Exception: pass

        # V3 I3 additive evidence table. The legacy trainer_countersignatures table is kept
        # untouched so historical V2 proofs are never rewritten. New V3 proofs support one
        # immutable countersignature per active trainer assigned to the slot.
        v3_i3_schema = [
        """CREATE TABLE IF NOT EXISTS trainer_countersignatures_v3 (
          id INTEGER PRIMARY KEY AUTOINCREMENT, slot_id INTEGER NOT NULL, trainer_id INTEGER, trainer_name TEXT NOT NULL,
          trainer_email TEXT, signed_at TEXT NOT NULL, declaration_text TEXT NOT NULL, signature_path TEXT,
          signature_sha256 TEXT, method TEXT NOT NULL DEFAULT 'MANUSCRITE', actor TEXT, ip_address TEXT, user_agent TEXT,
          legacy_source_id INTEGER UNIQUE, created_at TEXT NOT NULL,
          UNIQUE(slot_id,trainer_id), FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE,
          FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE SET NULL)"""
        ]
        for sql in v3_i3_schema: c.execute(text(sql))

        # V3 I4 planning coordination log. It records the propagation work created by a
        # validated planning change without coupling the core planning rules to email/Teams.
        v3_i4_schema = [
        """CREATE TABLE IF NOT EXISTS planning_change_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, slot_id INTEGER, change_type TEXT NOT NULL,
          actor TEXT NOT NULL, affected_participants INTEGER NOT NULL DEFAULT 0, affected_trainers INTEGER NOT NULL DEFAULT 0,
          attendance_synced INTEGER NOT NULL DEFAULT 0, quality_synced INTEGER NOT NULL DEFAULT 0, portals_synced INTEGER NOT NULL DEFAULT 1,
          teams_required INTEGER NOT NULL DEFAULT 0, teams_status TEXT NOT NULL DEFAULT 'NOT_ENABLED', notification_status TEXT NOT NULL DEFAULT 'PENDING',
          details_json TEXT, created_at TEXT NOT NULL, FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE,
          FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE SET NULL)"""
        ]
        for sql in v3_i4_schema: c.execute(text(sql))

        # V3 I6 generic import profiles. A profile belongs to an organization and
        # describes how its management workbook is read. Source files stay outside
        # SQLite; only mapping/configuration is stored here.
        v3_i6_schema = [
        """CREATE TABLE IF NOT EXISTS organization_import_profiles (
          id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL, code TEXT NOT NULL, name TEXT NOT NULL,
          source_type TEXT NOT NULL DEFAULT 'EXCEL', action_key TEXT NOT NULL, action_sheet TEXT NOT NULL DEFAULT 'CONV ADM',
          participant_sheet TEXT NOT NULL DEFAULT 'STAGIAIRE', mapping_json TEXT, config_json TEXT, active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(organization_id,code),
          FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE)"""
        ]
        for sql in v3_i6_schema: c.execute(text(sql))

        # V3 I7 Microsoft Teams / Graph.  These tables are additive and remain inert
        # until the TEAMS module is explicitly enabled for an action and Graph is configured.
        v3_i7_schema = [
        """CREATE TABLE IF NOT EXISTS teams_action_rooms (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL UNIQUE, provider TEXT NOT NULL DEFAULT 'MICROSOFT_TEAMS',
          organizer_user_id TEXT, organizer_upn TEXT, online_meeting_id TEXT, join_web_url TEXT, subject TEXT,
          strategy TEXT NOT NULL DEFAULT 'STABLE_ACTION_LINK', lifecycle_status TEXT NOT NULL DEFAULT 'PENDING',
          raw_json TEXT, last_sync_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE)""",
        """CREATE TABLE IF NOT EXISTS teams_occurrences (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_room_id INTEGER, action_id INTEGER NOT NULL, slot_id INTEGER NOT NULL UNIQUE,
          scheduled_start_utc TEXT NOT NULL, scheduled_end_utc TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PLANNED',
          attendance_report_id TEXT, attendance_synced_at TEXT, last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(action_room_id) REFERENCES teams_action_rooms(id) ON DELETE CASCADE,
          FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE)""",
        """CREATE TABLE IF NOT EXISTS teams_participant_roles (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, slot_id INTEGER, trainer_id INTEGER, email TEXT NOT NULL,
          display_name TEXT, entra_user_id TEXT, role TEXT NOT NULL DEFAULT 'PRESENTER', guest_status TEXT NOT NULL DEFAULT 'NOT_REQUIRED',
          invitation_id TEXT, invited_at TEXT, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          UNIQUE(action_id,slot_id,email), FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE,
          FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE, FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE SET NULL)""",
        """CREATE TABLE IF NOT EXISTS teams_attendance_reports (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_room_id INTEGER NOT NULL, occurrence_id INTEGER, report_id TEXT NOT NULL UNIQUE,
          meeting_start_utc TEXT, meeting_end_utc TEXT, total_participants INTEGER NOT NULL DEFAULT 0, raw_json TEXT, retrieved_at TEXT NOT NULL,
          FOREIGN KEY(action_room_id) REFERENCES teams_action_rooms(id) ON DELETE CASCADE,
          FOREIGN KEY(occurrence_id) REFERENCES teams_occurrences(id) ON DELETE SET NULL)""",
        """CREATE TABLE IF NOT EXISTS teams_attendance_records (
          id INTEGER PRIMARY KEY AUTOINCREMENT, report_row_id INTEGER NOT NULL, participant_id INTEGER, display_name TEXT, email TEXT,
          join_time_utc TEXT, leave_time_utc TEXT, duration_seconds INTEGER, role TEXT, identity_json TEXT, raw_json TEXT, created_at TEXT NOT NULL,
          FOREIGN KEY(report_row_id) REFERENCES teams_attendance_reports(id) ON DELETE CASCADE,
          FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE SET NULL)""",
        """CREATE TABLE IF NOT EXISTS teams_sync_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, slot_id INTEGER, event_type TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, details_json TEXT,
          created_at TEXT NOT NULL, processed_at TEXT, UNIQUE(action_id,slot_id,event_type),
          FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE)"""
        ]
        for sql in v3_i7_schema: c.execute(text(sql))

        # I9 H2.3: cryptographic fingerprints of Microsoft Graph evidence.
        for sql in [
            "ALTER TABLE teams_attendance_reports ADD COLUMN raw_sha256 TEXT",
            "ALTER TABLE teams_attendance_records ADD COLUMN raw_sha256 TEXT"
        ]:
            try: c.execute(text(sql))
            except Exception: pass

        # Copy legacy evidence once, without modifying the original record. When possible,
        # attach it to the V3 trainer assignment by email/name; otherwise keep trainer_id NULL.
        c.execute(text("""INSERT OR IGNORE INTO trainer_countersignatures_v3(
          slot_id,trainer_id,trainer_name,trainer_email,signed_at,declaration_text,signature_path,signature_sha256,method,actor,legacy_source_id,created_at)
          SELECT tc.slot_id,
                 COALESCE((SELECT st.trainer_id FROM slot_trainers st JOIN trainers t ON t.id=st.trainer_id
                           WHERE st.slot_id=tc.slot_id AND st.active=1 AND st.assignment_status='ACTIVE'
                             AND ((tc.trainer_email IS NOT NULL AND LOWER(t.email)=LOWER(tc.trainer_email))
                                  OR LOWER(t.full_name)=LOWER(tc.trainer_name)) ORDER BY st.id LIMIT 1),
                          (SELECT a.trainer_id FROM slots s JOIN actions a ON a.id=s.action_id WHERE s.id=tc.slot_id)),
                 tc.trainer_name,tc.trainer_email,tc.signed_at,tc.declaration_text,tc.signature_path,tc.signature_sha256,tc.method,tc.actor,tc.id,tc.signed_at
          FROM trainer_countersignatures tc"""))

        # V3 I3: automatic attendance reminders no longer exist. Preserve sent history,
        # neutralise only pending V2 reminders already present in a production database.
        c.execute(text("""UPDATE email_events SET status='SKIPPED',last_error='Désactivé par règle V3 I3'
          WHERE event_type IN ('RELANCE_1','RELANCE_2') AND status='PENDING'"""))

        # Idempotent V2 -> V3 backfill. V2 trainer_id remains untouched and becomes
        # the V3 referent plus principal on every existing slot.
        now_v3 = utcnow_iso()
        c.execute(text("""INSERT OR IGNORE INTO action_trainers(action_id,trainer_id,role,is_referent,active,created_at,updated_at)
          SELECT a.id,a.trainer_id,'REFERENT',1,1,:n,:n FROM actions a JOIN trainers t ON t.id=a.trainer_id WHERE a.trainer_id IS NOT NULL"""), {'n':now_v3})
        c.execute(text("""UPDATE action_trainers SET role='REFERENT',is_referent=1,active=1,updated_at=:n
          WHERE EXISTS (SELECT 1 FROM actions a WHERE a.id=action_trainers.action_id AND a.trainer_id=action_trainers.trainer_id)"""), {'n':now_v3})
        c.execute(text("""INSERT OR IGNORE INTO slot_trainers(slot_id,trainer_id,role,assignment_status,created_by,active,created_at,updated_at)
          SELECT s.id,a.trainer_id,'PRINCIPAL','ACTIVE','migration-v2',1,:n,:n
          FROM slots s JOIN actions a ON a.id=s.action_id JOIN trainers t ON t.id=a.trainer_id WHERE a.trainer_id IS NOT NULL"""), {'n':now_v3})
        c.execute(text("""INSERT OR IGNORE INTO trainer_assignment_history(scope_type,action_id,trainer_id,event_type,new_role,new_status,reason,actor,created_at,migration_key)
          SELECT 'ACTION',a.id,a.trainer_id,'MIGRATED_FROM_V2','REFERENT','ACTIVE','Migration additive V2.2 vers V3 I1','migration-v2',:n,
                 'V2_ACTION_'||a.id||'_'||a.trainer_id FROM actions a JOIN trainers t ON t.id=a.trainer_id WHERE a.trainer_id IS NOT NULL"""), {'n':now_v3})
        c.execute(text("""INSERT OR IGNORE INTO trainer_assignment_history(scope_type,action_id,slot_id,trainer_id,event_type,new_role,new_status,reason,actor,created_at,migration_key)
          SELECT 'SLOT',s.action_id,s.id,a.trainer_id,'MIGRATED_FROM_V2','PRINCIPAL','ACTIVE','Migration additive V2.2 vers V3 I1','migration-v2',:n,
                 'V2_SLOT_'||s.id||'_'||a.trainer_id FROM slots s JOIN actions a ON a.id=s.action_id JOIN trainers t ON t.id=a.trainer_id WHERE a.trainer_id IS NOT NULL"""), {'n':now_v3})

        # Mirror the four V2 modules and create the future V3 module switches disabled.
        # In particular, TEAMS is NEVER activated by migration or by the action modality.
        module_rows = [
            ('ATTENDANCE','use_attendance'), ('QUALITY_HOT','use_quality_hot'),
            ('QUALITY_COLD','use_quality_cold'), ('TRAINER_FEEDBACK','use_trainer_feedback')
        ]
        for module_code, col in module_rows:
            c.execute(text(f"""INSERT OR IGNORE INTO action_modules(action_id,module_code,enabled,enabled_at,enabled_by,created_at,updated_at)
              SELECT id,:m,CASE WHEN COALESCE({col},0)<>0 THEN 1 ELSE 0 END,
                     CASE WHEN COALESCE({col},0)<>0 THEN :n ELSE NULL END,'migration-v2',:n,:n FROM actions"""), {'m':module_code,'n':now_v3})
        for module_code in ('BENEFICIARY_PORTAL','COURSE_DOCUMENTS','CLIENT_TRANSMISSION','TEAMS'):
            c.execute(text("""INSERT OR IGNORE INTO action_modules(action_id,module_code,enabled,enabled_by,created_at,updated_at)
              SELECT id,:m,0,'migration-v2',:n,:n FROM actions"""), {'m':module_code,'n':now_v3})

        post_migrations = [
            "ALTER TABLE beneficiary_portal_accounts ADD COLUMN portal_warning_sent_at TEXT",
            "ALTER TABLE beneficiary_portal_accounts ADD COLUMN portal_purge_due_at TEXT",
            "ALTER TABLE client_transmissions ADD COLUMN campaign_id INTEGER",
            "ALTER TABLE client_transmissions ADD COLUMN claimed_at TEXT",
            "ALTER TABLE client_transmissions ADD COLUMN claim_token TEXT",
            "ALTER TABLE client_transmissions ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0",
        ]
        for sql in post_migrations:
            try: c.execute(text(sql))
            except Exception: pass
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_actions_status ON actions(status)",
            "CREATE INDEX IF NOT EXISTS ix_actions_org_agency ON actions(organization_id,agency_id)",
            "CREATE INDEX IF NOT EXISTS ix_participants_name ON participants(last_name,first_name)",
            "CREATE INDEX IF NOT EXISTS ix_email_events_due_status ON email_events(status,due_at)",
            "CREATE INDEX IF NOT EXISTS ix_quality_email_due_status ON quality_email_events(status,due_at)",
            "CREATE INDEX IF NOT EXISTS ix_quality_campaign_action ON quality_campaigns(action_id,status,campaign_kind)",
            "CREATE INDEX IF NOT EXISTS ix_trainer_reports_action ON trainer_reports(action_id,trainer_id,status)",
            "CREATE INDEX IF NOT EXISTS ix_trainer_password_resets_token ON trainer_password_resets(token,used_at)",
            "CREATE INDEX IF NOT EXISTS ix_beneficiaries_identity ON beneficiaries(last_name,first_name,birth_date)",
            "CREATE INDEX IF NOT EXISTS ix_participants_beneficiary ON participants(beneficiary_id)",
            "CREATE INDEX IF NOT EXISTS ix_document_refs_action ON document_references(action_id,deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_document_refs_beneficiary ON document_references(beneficiary_id,deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_action_trainers_action ON action_trainers(action_id,active,is_referent)",
            "CREATE INDEX IF NOT EXISTS ix_action_trainers_trainer ON action_trainers(trainer_id,active)",
            "CREATE INDEX IF NOT EXISTS ix_slot_trainers_slot ON slot_trainers(slot_id,active)",
            "CREATE INDEX IF NOT EXISTS ix_slot_trainers_trainer ON slot_trainers(trainer_id,active)",
            "CREATE INDEX IF NOT EXISTS ix_assignment_history_action ON trainer_assignment_history(action_id,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_action_modules_action ON action_modules(action_id,enabled)",
            "CREATE INDEX IF NOT EXISTS ix_import_profiles_org ON organization_import_profiles(organization_id,active)",
            "CREATE INDEX IF NOT EXISTS ix_teams_occurrences_action ON teams_occurrences(action_id,status)",
            "CREATE INDEX IF NOT EXISTS ix_teams_roles_action_slot ON teams_participant_roles(action_id,slot_id,active)",
            "CREATE INDEX IF NOT EXISTS ix_teams_reports_room ON teams_attendance_reports(action_room_id,retrieved_at)",
            "CREATE INDEX IF NOT EXISTS ix_teams_sync_status ON teams_sync_events(status,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_auth_sessions_subject ON auth_sessions(subject_type,subject_ref,revoked_at)",
            "CREATE INDEX IF NOT EXISTS ix_auth_sessions_expiry ON auth_sessions(expires_at,revoked_at)",
            "CREATE INDEX IF NOT EXISTS ix_communication_due_status ON communication_events(status,due_at)",
            "CREATE INDEX IF NOT EXISTS ix_communication_action ON communication_events(action_id,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_tool_catalog_active ON tool_catalog(active,prescription_allowed,tool_code)",
            "CREATE INDEX IF NOT EXISTS ix_tool_prescriptions_beneficiary ON tool_prescriptions(beneficiary_id,status,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_tool_prescriptions_action ON tool_prescriptions(action_id,status,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_prescription_tokens_expiry ON prescription_access_tokens(expires_at,revoked_at)",
            "CREATE INDEX IF NOT EXISTS ix_prescription_events_prescription ON prescription_events(prescription_id,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_connector_cursors_updated ON connector_cursors(updated_at)",
            "CREATE INDEX IF NOT EXISTS ix_study_exports_date ON study_export_events(exported_at,actor)",
            "CREATE INDEX IF NOT EXISTS ix_crm_contacts_status ON crm_contacts(status,updated_at)",
            "CREATE INDEX IF NOT EXISTS ix_crm_contacts_email ON crm_contacts(email)",
            "CREATE INDEX IF NOT EXISTS ix_crm_contacts_beneficiary ON crm_contacts(beneficiary_id)",
            "CREATE INDEX IF NOT EXISTS ix_contractualization_action ON contractualization_cases(action_id,status,updated_at)",
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
