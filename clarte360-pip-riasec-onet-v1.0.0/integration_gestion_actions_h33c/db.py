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
"""CREATE TABLE IF NOT EXISTS action_tool_permissions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, tool_id INTEGER NOT NULL, tool_code TEXT NOT NULL, allowed INTEGER NOT NULL DEFAULT 1,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(action_id,tool_id), FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(tool_id) REFERENCES tool_catalog(id) ON DELETE CASCADE
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

I9H28_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS beneficiary_reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, beneficiary_id INTEGER NOT NULL, report_type TEXT NOT NULL, subject TEXT NOT NULL,
 description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'NOUVEAU', quality_relevant INTEGER NOT NULL DEFAULT 1, attachment_path TEXT, attachment_name TEXT,
 admin_response TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, closed_at TEXT,
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(beneficiary_id) REFERENCES beneficiaries(id) ON DELETE CASCADE
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

CRM0_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS crm_tasks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id INTEGER NOT NULL, title TEXT NOT NULL, due_at TEXT, status TEXT NOT NULL DEFAULT 'A_FAIRE',
 notes TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT, updated_at TEXT NOT NULL,
 FOREIGN KEY(contact_id) REFERENCES crm_contacts(id) ON DELETE CASCADE
)""",
"""CREATE TABLE IF NOT EXISTS crm_action_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id INTEGER NOT NULL, action_id INTEGER NOT NULL, role TEXT NOT NULL DEFAULT 'CLIENT',
 created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(contact_id,action_id,role),
 FOREIGN KEY(contact_id) REFERENCES crm_contacts(id) ON DELETE CASCADE,
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE
)"""
]

PIP_LIAISON_B_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS external_incoming_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, event_id TEXT NOT NULL, event_type TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'RECU', received_at TEXT NOT NULL, processed_at TEXT, attempts INTEGER NOT NULL DEFAULT 0,
 last_error TEXT, payload_sha256 TEXT NOT NULL, metadata_json TEXT,
 UNIQUE(source,event_id)
)"""
]


PIP_LIAISON_C_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS crm_callback_notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id INTEGER NOT NULL, external_event_id TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL DEFAULT 'A_ENVOYER', requested_at TEXT NOT NULL, sent_at TEXT, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(contact_id) REFERENCES crm_contacts(id) ON DELETE CASCADE
)"""
]


PIP_LIAISON_F_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS prescription_documents (
 id INTEGER PRIMARY KEY AUTOINCREMENT, prescription_id TEXT NOT NULL, document_reference_id INTEGER NOT NULL, document_kind TEXT NOT NULL DEFAULT 'PIP_REPORT',
 source_event_id TEXT, source_reference TEXT, created_at TEXT NOT NULL,
 UNIQUE(prescription_id,document_kind), UNIQUE(source_event_id),
 FOREIGN KEY(prescription_id) REFERENCES tool_prescriptions(prescription_id) ON DELETE CASCADE,
 FOREIGN KEY(document_reference_id) REFERENCES document_references(id) ON DELETE CASCADE
)"""
]

INTERVENANTS_J0_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS professional_persons (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL UNIQUE, trainer_id INTEGER UNIQUE,
 principal_status TEXT NOT NULL DEFAULT 'CANDIDAT', candidate_work_status TEXT NOT NULL DEFAULT 'NOUVEAU',
 active INTEGER NOT NULL DEFAULT 1, supplier_id TEXT, qualification_review_due_at TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(principal_status IN ('CANDIDAT','INTERVENANT')),
 CHECK(candidate_work_status IN ('NOUVEAU','INCOMPLET','EN_ETUDE','COMPLEMENT_DEMANDE','ENTRETIEN_A_PREVOIR','PRET_DECISION','REFUSE','ABANDONNE','VALIDE')),
 FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS professional_person_status_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, old_principal_status TEXT, new_principal_status TEXT NOT NULL,
 old_work_status TEXT, new_work_status TEXT, old_active INTEGER, new_active INTEGER, reason TEXT, actor TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)"""
]


INTERVENANTS_J1_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS service_catalog (
 id INTEGER PRIMARY KEY AUTOINCREMENT, service_code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 family TEXT, description TEXT, delivery_scope TEXT NOT NULL DEFAULT 'MIXTE', action_types_json TEXT,
 active INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL DEFAULT 'MANUEL', current_version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(delivery_scope IN ('INDIVIDUEL','COLLECTIF','MIXTE')),
 CHECK(source IN ('SITE_CLARTE360','MANUEL','IMPORT'))
)""",
"""CREATE TABLE IF NOT EXISTS service_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, service_id INTEGER NOT NULL, version_no INTEGER NOT NULL,
 service_code TEXT NOT NULL, name TEXT NOT NULL, family TEXT, description TEXT, delivery_scope TEXT NOT NULL,
 action_types_json TEXT, active INTEGER NOT NULL, source TEXT NOT NULL, change_reason TEXT, changed_by TEXT NOT NULL,
 created_at TEXT NOT NULL, UNIQUE(service_id,version_no),
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS service_competency_criteria (
 id INTEGER PRIMARY KEY AUTOINCREMENT, service_id INTEGER NOT NULL, criterion_code TEXT NOT NULL,
 category TEXT NOT NULL, label TEXT NOT NULL, description TEXT, required INTEGER NOT NULL DEFAULT 0,
 weight REAL, minimum_level INTEGER NOT NULL DEFAULT 0, accepted_evidence_json TEXT, validity_months INTEGER,
 active INTEGER NOT NULL DEFAULT 1, current_version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(service_id,criterion_code),
 CHECK(category IN ('METIER_TECHNIQUE','PEDAGOGIQUE','ACCOMPAGNEMENT_COACHING','COMPORTEMENTAL','REGLEMENTAIRE')),
 CHECK(minimum_level BETWEEN 0 AND 4), CHECK(required IN (0,1)), CHECK(active IN (0,1)),
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS service_criterion_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, criterion_id INTEGER NOT NULL, service_id INTEGER NOT NULL, version_no INTEGER NOT NULL,
 criterion_code TEXT NOT NULL, category TEXT NOT NULL, label TEXT NOT NULL, description TEXT, required INTEGER NOT NULL,
 weight REAL, minimum_level INTEGER NOT NULL, accepted_evidence_json TEXT, validity_months INTEGER, active INTEGER NOT NULL,
 change_reason TEXT, changed_by TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(criterion_id,version_no),
 FOREIGN KEY(criterion_id) REFERENCES service_competency_criteria(id) ON DELETE RESTRICT,
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT
)"""
]


INTERVENANTS_J15_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS service_families (
 id INTEGER PRIMARY KEY AUTOINCREMENT, family_code TEXT NOT NULL UNIQUE, name TEXT NOT NULL UNIQUE,
 description TEXT, active INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 100,
 current_version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(active IN (0,1))
)""",
"""CREATE TABLE IF NOT EXISTS service_family_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, family_id INTEGER NOT NULL, version_no INTEGER NOT NULL,
 family_code TEXT NOT NULL, name TEXT NOT NULL, description TEXT, active INTEGER NOT NULL,
 sort_order INTEGER NOT NULL, change_reason TEXT, changed_by TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(family_id,version_no), FOREIGN KEY(family_id) REFERENCES service_families(id) ON DELETE RESTRICT
)"""
]


INTERVENANTS_J3_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS candidate_workflow_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, event_type TEXT NOT NULL,
 old_work_status TEXT, new_work_status TEXT, comment TEXT, actor TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS candidate_requests (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, request_text TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'OUVERTE', requested_by TEXT NOT NULL, requested_at TEXT NOT NULL,
 resolved_by TEXT, resolved_at TEXT, resolution_comment TEXT,
 CHECK(status IN ('OUVERTE','RESOLUE','ANNULEE')),
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS candidate_decisions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, decision TEXT NOT NULL,
 reason TEXT, decided_by TEXT NOT NULL, decided_at TEXT NOT NULL,
 CHECK(decision IN ('VALIDER','REFUSER','ABANDONNER')),
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)"""
]


INTERVENANTS_J21_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS professional_regulatory_status (
 professional_person_id TEXT PRIMARY KEY, ownership_mode TEXT NOT NULL DEFAULT 'PERSONAL_ACTIVITY',
 nda_status TEXT NOT NULL DEFAULT 'NON_RENSEIGNE', nda_number TEXT, nda_region TEXT, nda_declared_at TEXT, nda_notes TEXT,
 qualiopi_status TEXT NOT NULL DEFAULT 'NON_RENSEIGNE', qualiopi_certifier TEXT, qualiopi_certificate_ref TEXT,
 qualiopi_valid_from TEXT, qualiopi_valid_until TEXT, qualiopi_scope_training INTEGER NOT NULL DEFAULT 0,
 qualiopi_scope_bilan INTEGER NOT NULL DEFAULT 0, qualiopi_scope_vae INTEGER NOT NULL DEFAULT 0,
 qualiopi_scope_apprentissage INTEGER NOT NULL DEFAULT 0, qualiopi_notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(ownership_mode IN ('PERSONAL_ACTIVITY','SUPPLIER_PROJECTION')),
 CHECK(nda_status IN ('NON_RENSEIGNE','OUI','NON')),
 CHECK(qualiopi_status IN ('NON_RENSEIGNE','OUI','NON')),
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)"""
]

INTERVENANTS_J2_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS professional_profiles (
 professional_person_id TEXT PRIMARY KEY, title TEXT, summary TEXT, collaboration_type TEXT, origin TEXT NOT NULL DEFAULT 'ADMIN',
 email TEXT, phone TEXT, address_line1 TEXT, address_line2 TEXT, postal_code TEXT, city TEXT, country TEXT,
 website TEXT, linkedin_url TEXT, photo_stored_file_id INTEGER, notes_internal TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
 FOREIGN KEY(photo_stored_file_id) REFERENCES stored_files(id) ON DELETE SET NULL
)""",
"""CREATE TABLE IF NOT EXISTS professional_experiences (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, organization TEXT, role_title TEXT NOT NULL, description TEXT,
 start_date TEXT, end_date TEXT, current_role INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS professional_education (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, diploma_title TEXT NOT NULL, institution TEXT, field TEXT,
 obtained_date TEXT, description TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS professional_certifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, certification_type TEXT NOT NULL DEFAULT 'CERTIFICATION',
 name TEXT NOT NULL, issuer TEXT, reference TEXT, obtained_date TEXT, valid_until TEXT, description TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(certification_type IN ('CERTIFICATION','HABILITATION','ATTESTATION')),
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS professional_languages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, language TEXT NOT NULL, level TEXT, evidence TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(professional_person_id,language), FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS professional_specialties (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, specialty TEXT NOT NULL, notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(professional_person_id,specialty), FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS professional_documents (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, stored_file_id INTEGER NOT NULL, category TEXT NOT NULL, display_name TEXT NOT NULL,
 valid_from TEXT, valid_until TEXT, visibility TEXT NOT NULL DEFAULT 'INTERNE', notes TEXT, uploaded_by TEXT, created_at TEXT NOT NULL, archived_at TEXT,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
 FOREIGN KEY(stored_file_id) REFERENCES stored_files(id) ON DELETE RESTRICT
)"""
]

INTERVENANTS_J4_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS person_service_qualifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, service_id INTEGER NOT NULL,
 human_value INTEGER, human_comment TEXT, human_validated_by TEXT, human_validated_at TEXT, human_locked INTEGER NOT NULL DEFAULT 1,
 qualification_date TEXT, review_due_at TEXT, ai_value INTEGER, ai_confidence REAL, ai_evidence_json TEXT, ai_updated_at TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(professional_person_id,service_id),
 CHECK(human_value IS NULL OR human_value BETWEEN 0 AND 4), CHECK(ai_value IS NULL OR ai_value BETWEEN 0 AND 4), CHECK(human_locked IN (0,1)),
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS qualification_criterion_assessments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, service_id INTEGER NOT NULL, criterion_id INTEGER NOT NULL,
 human_value INTEGER, human_comment TEXT, human_validated_by TEXT, human_validated_at TEXT, human_locked INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(professional_person_id,criterion_id),
 CHECK(human_value IS NULL OR human_value BETWEEN 0 AND 4), CHECK(human_locked IN (0,1)),
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT,
 FOREIGN KEY(criterion_id) REFERENCES service_competency_criteria(id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS qualification_evidence (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, service_id INTEGER NOT NULL, criterion_id INTEGER,
 professional_document_id INTEGER, evidence_type TEXT NOT NULL DEFAULT 'AUTRE', evidence_text TEXT, source_label TEXT,
 verified_by TEXT, verified_at TEXT, created_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT,
 FOREIGN KEY(criterion_id) REFERENCES service_competency_criteria(id) ON DELETE RESTRICT,
 FOREIGN KEY(professional_document_id) REFERENCES professional_documents(id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS qualification_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, service_id INTEGER NOT NULL, criterion_id INTEGER,
 event_type TEXT NOT NULL, old_human_value INTEGER, new_human_value INTEGER, comment TEXT, actor TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT,
 FOREIGN KEY(criterion_id) REFERENCES service_competency_criteria(id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS ai_qualification_evidence_proposals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, service_id INTEGER NOT NULL, criterion_id INTEGER, professional_document_id INTEGER,
 ai_run_id INTEGER, evidence_index INTEGER, evidence_text TEXT NOT NULL, source_label TEXT, supports_level INTEGER, confidence REAL, identity_status TEXT NOT NULL DEFAULT 'A_VERIFIER',
 status TEXT NOT NULL DEFAULT 'PROPOSEE', decided_by TEXT, decided_at TEXT, decision_comment TEXT, accepted_evidence_id INTEGER, created_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT,
 FOREIGN KEY(criterion_id) REFERENCES service_competency_criteria(id) ON DELETE RESTRICT,
 FOREIGN KEY(professional_document_id) REFERENCES professional_documents(id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS ai_criterion_proposals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, service_id INTEGER NOT NULL, criterion_id INTEGER NOT NULL, ai_run_id INTEGER,
 proposed_level INTEGER NOT NULL, confidence REAL, rationale TEXT, status TEXT NOT NULL DEFAULT 'PROPOSEE', decided_by TEXT, decided_at TEXT, decision_comment TEXT, created_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT,
 FOREIGN KEY(criterion_id) REFERENCES service_competency_criteria(id) ON DELETE RESTRICT
)"""
]



INTERVENANTS_J5_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS ai_analysis_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, service_id INTEGER NOT NULL,
 provider TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL, request_hash TEXT NOT NULL,
 status TEXT NOT NULL, input_summary_json TEXT, output_json TEXT, error_text TEXT,
 input_tokens INTEGER, output_tokens INTEGER, actor TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT
)"""
]

INTERVENANTS_J14_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS professional_global_ai_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL, request_hash TEXT NOT NULL,
 status TEXT NOT NULL, selected_document_ids_json TEXT, output_json TEXT, input_tokens INTEGER, output_tokens INTEGER, actor TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)""",
"""CREATE TABLE IF NOT EXISTS professional_ai_suggestions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, run_id INTEGER NOT NULL, suggestion_type TEXT NOT NULL, payload_json TEXT NOT NULL, source_document_id INTEGER,
 status TEXT NOT NULL DEFAULT 'PROPOSE', reviewed_by TEXT, reviewed_at TEXT, created_at TEXT NOT NULL,
 CHECK(status IN ('PROPOSE','ACCEPTE','REJETE')),
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT,
 FOREIGN KEY(run_id) REFERENCES professional_global_ai_runs(id) ON DELETE RESTRICT,
 FOREIGN KEY(source_document_id) REFERENCES professional_documents(id) ON DELETE RESTRICT
)"""
]

INTERVENANTS_J11_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS action_service_requirements (
 action_id INTEGER PRIMARY KEY, service_id INTEGER NOT NULL, minimum_human_level INTEGER NOT NULL DEFAULT 3,
 require_required_complete INTEGER NOT NULL DEFAULT 0, configured_by TEXT NOT NULL, configured_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(minimum_human_level BETWEEN 0 AND 4), CHECK(require_required_complete IN (0,1)),
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE,
 FOREIGN KEY(service_id) REFERENCES service_catalog(id) ON DELETE RESTRICT
)"""
]

INTERVENANTS_J10_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS professional_supplier_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, supplier_id TEXT NOT NULL,
 relationship_type TEXT NOT NULL DEFAULT 'PROFESSIONAL', valid_from TEXT, valid_to TEXT, source_system TEXT NOT NULL DEFAULT 'GESTION_INTERVENANTS',
 status TEXT NOT NULL DEFAULT 'ACTIVE', remote_link_id TEXT, last_sync_at TEXT, sync_status TEXT NOT NULL DEFAULT 'LOCAL', sync_error TEXT,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(status IN ('ACTIVE','INACTIVE')), CHECK(sync_status IN ('LOCAL','SYNCHRONISE','ERREUR')),
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)"""
]

INTERVENANTS_J8_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS professional_cv_generations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, audience TEXT NOT NULL,
 version_no INTEGER NOT NULL, file_name TEXT NOT NULL, sha256 TEXT NOT NULL, generated_by TEXT NOT NULL, generated_at TEXT NOT NULL,
 CHECK(audience IN ('INTERNE','CLIENT')),
 UNIQUE(professional_person_id,audience,version_no),
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)"""
]

INTERVENANTS_J7_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS professional_maintenance_actions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, professional_person_id TEXT NOT NULL, alert_key TEXT NOT NULL,
 action_type TEXT NOT NULL, comment TEXT, snooze_until TEXT, actor TEXT NOT NULL, created_at TEXT NOT NULL,
 CHECK(action_type IN ('TRAITE','REPORTE','ROUVERT')),
 FOREIGN KEY(professional_person_id) REFERENCES professional_persons(professional_person_id) ON DELETE RESTRICT
)"""
]

I9J2_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS quality_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, organization_id INTEGER, agency_id INTEGER, action_id INTEGER, slot_id INTEGER, campaign_id INTEGER,
 beneficiary_id INTEGER, trainer_id INTEGER, external_contact_id INTEGER, family TEXT NOT NULL, event_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'NOUVEAU',
 detected_at TEXT NOT NULL, origin TEXT NOT NULL DEFAULT 'MANUEL', subject TEXT NOT NULL, description TEXT, theme TEXT, severity TEXT NOT NULL DEFAULT 'MINEURE',
 urgency TEXT NOT NULL DEFAULT 'NORMALE', criticality TEXT, recurrence INTEGER NOT NULL DEFAULT 0, qualification TEXT, owner_type TEXT, owner_ref TEXT, owner_name TEXT,
 immediate_action TEXT, cause_analysis TEXT, due_at TEXT, effectiveness_criteria TEXT, effectiveness_result TEXT, effectiveness_checked_at TEXT, effectiveness_checked_by TEXT,
 closure_decision TEXT, closure_comment TEXT, closed_at TEXT, closed_by TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE SET NULL, FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE SET NULL,
 FOREIGN KEY(campaign_id) REFERENCES quality_campaigns(id) ON DELETE SET NULL, FOREIGN KEY(beneficiary_id) REFERENCES beneficiaries(id) ON DELETE SET NULL,
 FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE SET NULL
)""",
"""CREATE TABLE IF NOT EXISTS quality_event_actions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, quality_event_id INTEGER NOT NULL, action_kind TEXT NOT NULL DEFAULT 'CORRECTIVE', title TEXT NOT NULL, description TEXT,
 owner_type TEXT, owner_ref TEXT, owner_name TEXT, due_at TEXT, status TEXT NOT NULL DEFAULT 'A_FAIRE', evidence_ref TEXT, effectiveness_result TEXT, completed_at TEXT,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(quality_event_id) REFERENCES quality_events(id) ON DELETE CASCADE
)""",
"""CREATE TABLE IF NOT EXISTS quality_event_messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, quality_event_id INTEGER NOT NULL, direction TEXT NOT NULL DEFAULT 'INTERNE', author TEXT NOT NULL, recipient TEXT, message TEXT NOT NULL,
 channel TEXT NOT NULL DEFAULT 'NOTE', created_at TEXT NOT NULL, FOREIGN KEY(quality_event_id) REFERENCES quality_events(id) ON DELETE CASCADE
)""",
"""CREATE TABLE IF NOT EXISTS quality_contacts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER, first_name TEXT, last_name TEXT NOT NULL, organization_name TEXT, job_title TEXT, email TEXT, phone TEXT,
 domain TEXT, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
)""",
"""CREATE TABLE IF NOT EXISTS quality_review_points (
 id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL, response_id INTEGER, question_id INTEGER NOT NULL, action_id INTEGER NOT NULL, score REAL, comment TEXT,
 status TEXT NOT NULL DEFAULT 'A_EXAMINER', decision TEXT, decision_comment TEXT, quality_event_id INTEGER, created_at TEXT NOT NULL, reviewed_at TEXT, reviewed_by TEXT,
 UNIQUE(campaign_id,question_id), FOREIGN KEY(campaign_id) REFERENCES quality_campaigns(id) ON DELETE CASCADE, FOREIGN KEY(response_id) REFERENCES quality_responses(id) ON DELETE SET NULL,
 FOREIGN KEY(question_id) REFERENCES questionnaire_questions(id), FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE, FOREIGN KEY(quality_event_id) REFERENCES quality_events(id) ON DELETE SET NULL
)""",
"""CREATE TABLE IF NOT EXISTS external_quality_contacts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER, contact_kind TEXT NOT NULL, company TEXT, first_name TEXT, last_name TEXT NOT NULL, job_title TEXT, email TEXT NOT NULL, phone TEXT,
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
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
        for sql in I9H28_SCHEMA:
            c.execute(text(sql))
        for sql in I9E_SCHEMA:
            c.execute(text(sql))
        for sql in I9F_SCHEMA:
            c.execute(text(sql))
        for sql in I9G_SCHEMA:
            c.execute(text(sql))
        for sql in CRM0_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J0_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J1_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J2_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J21_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J3_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J4_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J5_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J7_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J8_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J10_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J11_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J14_SCHEMA:
            c.execute(text(sql))
        for sql in INTERVENANTS_J15_SCHEMA:
            c.execute(text(sql))
        for sql in I9J2_SCHEMA:
            c.execute(text(sql))
        for sql in PIP_LIAISON_B_SCHEMA:
            c.execute(text(sql))
        for sql in PIP_LIAISON_C_SCHEMA:
            c.execute(text(sql))
        for sql in PIP_LIAISON_F_SCHEMA:
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
            "ALTER TABLE quality_campaigns ADD COLUMN external_contact_id INTEGER",
            "ALTER TABLE quality_campaigns ADD COLUMN external_recipient_email TEXT",
            "ALTER TABLE quality_campaigns ADD COLUMN external_recipient_name TEXT",
            "ALTER TABLE participants ADD COLUMN pin_recovery_cipher TEXT",
            "ALTER TABLE trainers ADD COLUMN reset_requested_at TEXT",
            "ALTER TABLE trainers ADD COLUMN can_upload_documents INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE trainers ADD COLUMN microsoft_email TEXT",
            "ALTER TABLE trainers ADD COLUMN entra_user_id TEXT",
            "ALTER TABLE trainers ADD COLUMN entra_status TEXT NOT NULL DEFAULT 'UNCHECKED'",
            "ALTER TABLE trainers ADD COLUMN entra_last_verified_at TEXT",
            "ALTER TABLE trainers ADD COLUMN entra_creation_requested_at TEXT",
            "ALTER TABLE trainers ADD COLUMN entra_creation_requested_by TEXT",
            "ALTER TABLE trainers ADD COLUMN professional_person_id TEXT",
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
        # trainers may not exist yet on a fresh database because the historical schema
        # creates it in the extra block below. The same additive column is therefore
        # ensured again after CREATE TABLE, keeping upgrades and fresh installs equivalent.
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
        try: c.execute(text("ALTER TABLE trainers ADD COLUMN professional_person_id TEXT"))
        except Exception: pass

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
            "ALTER TABLE trainer_reports ADD COLUMN admin_response TEXT",
            "ALTER TABLE trainer_reports ADD COLUMN closed_at TEXT",
            "ALTER TABLE quality_issues ADD COLUMN source_role TEXT",
            "ALTER TABLE quality_issues ADD COLUMN source_ref TEXT",
            "ALTER TABLE quality_issues ADD COLUMN updated_at TEXT",
        ]
        for sql in post_migrations:
            try: c.execute(text(sql))
            except Exception: pass
        for sql in [
            "ALTER TABLE person_service_qualifications ADD COLUMN ai_rationale TEXT",
            "ALTER TABLE person_service_qualifications ADD COLUMN ai_missing_json TEXT",
            "ALTER TABLE person_service_qualifications ADD COLUMN ai_provider TEXT",
            "ALTER TABLE person_service_qualifications ADD COLUMN ai_model TEXT",
            "ALTER TABLE person_service_qualifications ADD COLUMN ai_prompt_version TEXT",
            "ALTER TABLE person_service_qualifications ADD COLUMN ai_run_id INTEGER"
        ]:
            try: c.execute(text(sql))
            except Exception: pass

        # Intervenants J15: families become master data and criteria carry their origin.
        for sql in [
            "ALTER TABLE service_catalog ADD COLUMN family_id INTEGER",
            "ALTER TABLE service_competency_criteria ADD COLUMN source_kind TEXT",
            "ALTER TABLE service_competency_criteria ADD COLUMN source_reference TEXT",
            "ALTER TABLE service_criterion_versions ADD COLUMN source_kind TEXT",
            "ALTER TABLE service_criterion_versions ADD COLUMN source_reference TEXT"
        ]:
            try: c.execute(text(sql))
            except Exception: pass

        # Intervenants J0: every historical trainer receives a stable professional person identity.
        # This is an identity migration only: no qualification or competence is inferred.
        trainer_rows = c.execute(text("SELECT id, professional_person_id, active, created_at, updated_at FROM trainers ORDER BY id")).mappings().all()
        for tr in trainer_rows:
            ppid = (tr.get("professional_person_id") or "").strip() or f"PP-{int(tr['id']):08d}"
            c.execute(text("UPDATE trainers SET professional_person_id=:p WHERE id=:i AND (professional_person_id IS NULL OR professional_person_id='')"), {"p": ppid, "i": tr["id"]})
            c.execute(text("""INSERT OR IGNORE INTO professional_persons(
                professional_person_id,trainer_id,principal_status,candidate_work_status,active,created_at,updated_at)
                VALUES(:p,:t,'INTERVENANT','VALIDE',:a,:c,:u)"""), {
                "p": ppid, "t": tr["id"], "a": 1 if tr.get("active") else 0,
                "c": tr.get("created_at") or utcnow_iso(), "u": tr.get("updated_at") or utcnow_iso()
            })

        # Intervenants J1R: catalogue V1 Clarte360, administrable et evolutif.
        # Les univers visibles restent metier (Bilan, Formations, Coaching, Conseil, Accompagnements) :
        # aucune etiquette Qualiopi n est affichee dans les listes de prestations.
        initial_services = [
            ('BILAN_COMPETENCES','Bilan de compétences','Bilan de compétences','INDIVIDUEL'),
            ('FORMATION_POSTURE_DIRIGEANT_LEADERSHIP','Développer sa posture de dirigeant et son leadership','Formations','INDIVIDUEL'),
            ('FORMATION_MANAGER_FAIRE_GRANDIR_EQUIPE','Manager et faire grandir ses équipes','Formations','MIXTE'),
            ('FORMATION_COMMUNIQUER_IMPACT_INFLUENCE','Communiquer avec impact et développer son influence professionnelle','Formations','MIXTE'),
            ('FORMATION_ACCOMPAGNER_CHANGEMENT','Accompagner le changement et mobiliser les équipes','Formations','MIXTE'),
            ('FORMATION_PILOTER_PERFORMANCE_ECO_FIN','Piloter la performance économique et financière de son activité','Formations','INDIVIDUEL'),
            ('FORMATION_DEVELOPPEMENT_COMMERCIAL','Développer son activité commerciale et fidéliser ses clients','Formations','MIXTE'),
            ('FORMATION_CONCEVOIR_PILOTER_EVALUER','Concevoir, piloter et évaluer des actions de formation','Formations','MIXTE'),
            ('FORMATION_QUALITE_CERTIFICATION','Piloter la qualité et préparer sa certification Qualiopi','Formations','MIXTE'),
            ('FORMATION_REGLEMENTATION_OF','Maîtriser les obligations réglementaires d’un organisme de formation','Formations','MIXTE'),
            ('FORMATION_GESTION_ADMIN_SOCIALE_FISCALE','Organiser la gestion administrative, sociale et fiscale de son entreprise','Formations','INDIVIDUEL'),
            ('FORMATION_PILOTAGE_OF_CONSEIL_SERVICES','Structurer et piloter un organisme de formation, de conseil et de services','Formations','INDIVIDUEL'),
            ('FORMATION_PREVENTION_RISQUES_SANTE_SECURITE','Prévenir les risques professionnels et développer la culture santé-sécurité','Formations','MIXTE'),
            ('FORMATION_DEMARCHE_QHSE','Structurer et piloter une démarche QHSE','Formations','MIXTE'),
            ('FORMATION_RSE_PERFORMANCE_DURABLE','Faire de la RSE un levier de performance durable','Formations','MIXTE'),
            ('COACHING_PROFESSIONNEL_INDIVIDUEL','Coaching professionnel individuel','Coaching','INDIVIDUEL'),
            ('COACHING_CARRIERE_TRANSITION','Coaching de carrière et transition professionnelle','Coaching','INDIVIDUEL'),
            ('COACHING_DIRIGEANT_ENTREPRENEUR','Coaching de dirigeant et d’entrepreneur','Coaching','INDIVIDUEL'),
            ('COACHING_MANAGERIAL_PRISE_FONCTION','Coaching managérial et prise de fonction','Coaching','INDIVIDUEL'),
            ('COACHING_COLLECTIF_EQUIPE','Coaching collectif et coaching d’équipe','Coaching','COLLECTIF'),
            ('CONSEIL_STRATEGIQUE_DECISION','Conseil stratégique et aide à la décision','Conseil','MIXTE'),
            ('CONSEIL_STRUCTURATION_ORGANISATION_PILOTAGE','Conseil en structuration, organisation et pilotage','Conseil','MIXTE'),
            ('CONSEIL_QHSE_SANTE_RSE','Conseil QHSE, santé au travail et RSE','Conseil','MIXTE'),
            ('CONSEIL_INGENIERIE_QUALITE_FORMATION','Conseil en ingénierie, qualité et conformité de la formation professionnelle','Conseil','MIXTE'),
            ('ACCOMPAGNEMENT_TRANSFORMATIONS_CHANGEMENT','Accompagnement des transformations et du changement','Accompagnements','MIXTE'),
            ('ACCOMPAGNEMENT_COHESION_ALIGNEMENT','Cohésion, alignement et performance collective','Accompagnements','COLLECTIF'),
        ]
        # Nettoyage controle du tout premier seed J1 : il n a jamais vocation a rester la nomenclature metier.
        legacy_j1_codes = (
            'COACHING_PROFESSIONNEL','QHSE_LEADER_INFLUENCE','ENTREPRENEUR_CREATION_STRUCTURATION',
            'SALARIE_PERFORMANCE_EVOLUTION','TRANSITION_CHANGEMENT_CAP','CONSEIL_STRATEGIQUE',
            'COHESION_ALIGNEMENT','LEADERSHIP_COLLECTIF','ACCOMPAGNEMENT_CHANGEMENT',
            'FORMATIONS_CIBLEES','FORMATIONS_COMPETENCES_TERRAIN','COACHING_COLLECTIF'
        )
        for legacy_code in legacy_j1_codes:
            old = c.execute(text("SELECT id FROM service_catalog WHERE service_code=:c AND source='SITE_CLARTE360'"), {'c':legacy_code}).mappings().first()
            if old:
                oid=old['id']
                c.execute(text("DELETE FROM service_criterion_versions WHERE criterion_id IN (SELECT id FROM service_competency_criteria WHERE service_id=:i)"), {'i':oid})
                c.execute(text("DELETE FROM service_competency_criteria WHERE service_id=:i"), {'i':oid})
                c.execute(text("DELETE FROM service_versions WHERE service_id=:i"), {'i':oid})
                c.execute(text("DELETE FROM service_catalog WHERE id=:i"), {'i':oid})
        j1_now=utcnow_iso()
        for code,name,family,scope in initial_services:
            c.execute(text("""INSERT OR IGNORE INTO service_catalog(
                service_code,name,family,delivery_scope,active,source,current_version,created_at,updated_at)
                VALUES(:c,:n,:f,:s,1,'SITE_CLARTE360',1,:d,:d)"""), {'c':code,'n':name,'f':family,'s':scope,'d':j1_now})
            row=c.execute(text("SELECT * FROM service_catalog WHERE service_code=:c"),{'c':code}).mappings().first()
            if row:
                c.execute(text("""INSERT OR IGNORE INTO service_versions(
                    service_id,version_no,service_code,name,family,description,delivery_scope,action_types_json,active,source,change_reason,changed_by,created_at)
                    VALUES(:i,1,:c,:n,:f,:d,:s,:a,:x,:o,'Initialisation catalogue V1 J1R','migration-j1r',:t)"""),
                    {'i':row['id'],'c':row['service_code'],'n':row['name'],'f':row.get('family'),'d':row.get('description'),
                     's':row['delivery_scope'],'a':row.get('action_types_json'),'x':row['active'],'o':row['source'],'t':j1_now})

        # Intervenants J15: referentiel maitre des familles. La famille n'est plus un texte libre.
        j15_now=utcnow_iso()
        family_seed = [
            ('BILAN_COMPETENCES','Bilan de compétences','Dispositif Bilan de compétences',10),
            ('FORMATIONS','Formations','Prestations de formation',20),
            ('COACHING','Coaching','Prestations de coaching professionnel',30),
            ('CONSEIL','Conseil','Prestations de conseil',40),
            ('ACCOMPAGNEMENTS','Accompagnements','Prestations d’accompagnement collectif ou organisationnel',50),
        ]
        for fcode,fname,fdesc,forder in family_seed:
            c.execute(text("""INSERT OR IGNORE INTO service_families(family_code,name,description,active,sort_order,current_version,created_at,updated_at)
              VALUES(:c,:n,:d,1,:o,1,:t,:t)"""),{'c':fcode,'n':fname,'d':fdesc,'o':forder,'t':j15_now})
            fr=c.execute(text('SELECT * FROM service_families WHERE family_code=:c'),{'c':fcode}).mappings().first()
            if fr:
                c.execute(text("""INSERT OR IGNORE INTO service_family_versions(family_id,version_no,family_code,name,description,active,sort_order,change_reason,changed_by,created_at)
                  VALUES(:i,1,:c,:n,:d,1,:o,'Initialisation familles J15','migration-j15',:t)"""),{'i':fr['id'],'c':fcode,'n':fname,'d':fdesc,'o':forder,'t':j15_now})
                c.execute(text("UPDATE service_catalog SET family_id=:i,family=:n WHERE LOWER(COALESCE(family,''))=LOWER(:n)"),{'i':fr['id'],'n':fname})

        # Referentiel initial de criteres : adaptation metier Clarte360, administrable et versionnee.
        # Il sert de grille d'instruction humaine ; il ne constitue ni un test ni une qualification automatique.
        common_evidence=json.dumps(['CV','DIPLOME','CERTIFICATION','ATTESTATION','EXPERIENCE','MISSION','REFERENCE','ENTRETIEN','DOCUMENT'],ensure_ascii=False)
        criteria_seed=[]
        def addcrit(service_code, code, category, label, description, required=1, min_level=3, evidence=None, source='ADAPTATION_CLARTE360'):
            criteria_seed.append((service_code,code,category,label,description,required,min_level,json.dumps(evidence or ['CV','EXPERIENCE','MISSION','REFERENCE','ENTRETIEN','DOCUMENT'],ensure_ascii=False),source))

        # Bilan de competences : une seule prestation, grille d'instruction Clarte360.
        addcrit('BILAN_COMPETENCES','BC_CADRE_FINALITE','REGLEMENTAIRE','Maîtriser le cadre, la finalité et les limites du bilan de compétences','Savoir expliquer le dispositif, son objectif, la confidentialité, les responsabilités et les limites de l’accompagnement.',1,3,['FORMATION','CERTIFICATION','ATTESTATION','EXPERIENCE','ENTRETIEN','DOCUMENT'])
        addcrit('BILAN_COMPETENCES','BC_ANALYSE_DEMANDE','ACCOMPAGNEMENT_COACHING','Analyser la demande et clarifier les objectifs du bénéficiaire','Conduire l’analyse de la demande, reformuler les attentes et poser un cadre de travail individualisé.',1,3)
        addcrit('BILAN_COMPETENCES','BC_CONDUITE_PHASES','METIER_TECHNIQUE','Conduire un bilan de compétences de manière structurée','Maîtriser un déroulé cohérent de l’accueil à la conclusion, avec investigation, synthèse et plan d’action.',1,3,['FORMATION','ATTESTATION','EXPERIENCE','MISSION','REFERENCE','ENTRETIEN','DOCUMENT'])
        addcrit('BILAN_COMPETENCES','BC_EXPLORATION','ACCOMPAGNEMENT_COACHING','Explorer compétences, motivations, intérêts, valeurs et contraintes','Utiliser l’entretien et des outils adaptés sans enfermer la personne dans une typologie.',1,3)
        addcrit('BILAN_COMPETENCES','BC_PROJET_VERIFICATION','METIER_TECHNIQUE','Accompagner l’élaboration et la vérification du projet professionnel','Aider à formuler des hypothèses, les confronter à la réalité et construire un plan d’action réaliste.',1,3)
        addcrit('BILAN_COMPETENCES','BC_POSTURE_AUTONOMIE','COMPORTEMENTAL','Adopter une posture favorisant l’autonomie et la décision du bénéficiaire','Questionner, reformuler et faire réfléchir sans décider à la place de la personne.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
        addcrit('BILAN_COMPETENCES','BC_SYNTHESE','METIER_TECHNIQUE','Produire une synthèse utile, fidèle et exploitable','Structurer une synthèse qui reprend les éléments utiles au bénéficiaire et son plan d’action, sans inventer de conclusions.',1,3,['EXPERIENCE','MISSION','REFERENCE','DOCUMENT','ENTRETIEN'])
        addcrit('BILAN_COMPETENCES','BC_CONFIDENTIALITE','REGLEMENTAIRE','Garantir confidentialité, consentement et traçabilité du dossier','Appliquer les règles internes de confidentialité, de consentement, de droits d’accès et de conservation des informations.',1,3,['FORMATION','ATTESTATION','EXPERIENCE','ENTRETIEN','DOCUMENT'])

        formation_codes=[x[0] for x in initial_services if x[2]=='Formations']
        for sc in formation_codes:
            sname=next(x[1] for x in initial_services if x[0]==sc)
            addcrit(sc,'FORM_EXPERTISE_DOMAINE','METIER_TECHNIQUE',f'Maîtriser le domaine : {sname}',f'Démontrer une maîtrise professionnelle suffisante du contenu et des situations de travail liées à « {sname} ».',1,3,['CV','DIPLOME','CERTIFICATION','ATTESTATION','EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'FORM_CONCEPTION','PEDAGOGIQUE','Concevoir une séquence cohérente avec les objectifs et le public','Définir objectifs, progression, méthodes, supports et activités adaptés au public et au contexte.',1,3,['CV','EXPERIENCE','MISSION','REFERENCE','ENTRETIEN','DOCUMENT'])
            addcrit(sc,'FORM_ANIMATION','PEDAGOGIQUE','Animer et adapter la formation en situation','Créer les conditions d’apprentissage, expliquer clairement, faire pratiquer et ajuster l’animation aux besoins observés.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'FORM_EVALUATION','PEDAGOGIQUE','Évaluer les acquis et donner un retour utile','Mettre en œuvre des évaluations adaptées et exploiter les résultats pour faire progresser les participants.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN','DOCUMENT'])
            addcrit(sc,'FORM_POSTURE','COMPORTEMENTAL','Adopter une posture professionnelle de formateur','Faire preuve de clarté, écoute, respect, adaptation et capacité à gérer un groupe ou une situation pédagogique.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'FORM_TRACABILITE','REGLEMENTAIRE','Respecter le cadre administratif, qualité et traçabilité de la formation','Renseigner les éléments nécessaires au suivi de la formation et appliquer les procédures Clarté360 liées à la preuve de réalisation.',1,2,['EXPERIENCE','MISSION','ATTESTATION','ENTRETIEN','DOCUMENT'])

        coaching_codes=[x[0] for x in initial_services if x[2]=='Coaching']
        for sc in coaching_codes:
            sname=next(x[1] for x in initial_services if x[0]==sc)
            addcrit(sc,'COACH_CADRE','ACCOMPAGNEMENT_COACHING','Poser et tenir le cadre de coaching','Contractualiser les objectifs, rôles, limites, confidentialité et modalités du coaching.',1,3,['CV','DIPLOME','CERTIFICATION','ATTESTATION','EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'COACH_ECOUTE_QUESTIONNEMENT','ACCOMPAGNEMENT_COACHING','Mobiliser écoute active, questionnement et reformulation','Favoriser prise de conscience et réflexion sans imposer de solution.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'COACH_PROCESSUS','ACCOMPAGNEMENT_COACHING','Conduire un processus orienté objectifs et passage à l’action','Structurer l’accompagnement, suivre les objectifs et soutenir la responsabilisation du client.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'COACH_AUTONOMIE','COMPORTEMENTAL','Préserver autonomie, consentement et absence de manipulation','Maintenir une posture respectueuse de la personne, de ses choix et de son rythme.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'COACH_CONTEXTE','METIER_TECHNIQUE',f'Être pertinent dans le contexte : {sname}',f'Disposer d’une expérience ou de repères suffisants pour accompagner de façon crédible dans le contexte « {sname} » sans se substituer à l’expertise du client.',1,2,['CV','EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'COACH_DEONTOLOGIE','REGLEMENTAIRE','Appliquer confidentialité, déontologie et limites d’intervention','Identifier les limites du coaching, les situations nécessitant orientation ou intervention d’un autre professionnel et protéger les informations confiées.',1,3,['FORMATION','CERTIFICATION','ATTESTATION','EXPERIENCE','ENTRETIEN','DOCUMENT'])

        conseil_codes=[x[0] for x in initial_services if x[2]=='Conseil']
        for sc in conseil_codes:
            sname=next(x[1] for x in initial_services if x[0]==sc)
            addcrit(sc,'CONS_EXPERTISE','METIER_TECHNIQUE',f'Maîtriser le domaine de conseil : {sname}',f'Démontrer une expertise professionnelle directement pertinente pour « {sname} ».',1,3,['CV','DIPLOME','CERTIFICATION','EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'CONS_DIAGNOSTIC','METIER_TECHNIQUE','Analyser la situation et poser un diagnostic argumenté','Recueillir les faits, identifier enjeux, écarts et contraintes et distinguer constats, hypothèses et recommandations.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN','DOCUMENT'])
            addcrit(sc,'CONS_RECOMMANDATIONS','METIER_TECHNIQUE','Formuler des recommandations opérationnelles et proportionnées','Proposer des options explicites, argumentées, réalisables et adaptées au contexte du client.',1,3,['EXPERIENCE','MISSION','REFERENCE','DOCUMENT','ENTRETIEN'])
            addcrit(sc,'CONS_ACCOMP_MEO','ACCOMPAGNEMENT_COACHING','Accompagner la mise en œuvre sans se substituer au décideur','Aider à prioriser, planifier et suivre les actions tout en laissant la décision au client.',0,2,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'CONS_CONFIDENTIALITE','COMPORTEMENTAL','Garantir confidentialité, indépendance et clarté de posture','Préserver les informations confiées, expliciter les limites et éviter les conflits de rôles.',1,3,['EXPERIENCE','REFERENCE','ENTRETIEN','DOCUMENT'])

        accompagnement_codes=[x[0] for x in initial_services if x[2]=='Accompagnements']
        for sc in accompagnement_codes:
            sname=next(x[1] for x in initial_services if x[0]==sc)
            addcrit(sc,'ACC_DIAGNOSTIC','METIER_TECHNIQUE',f'Comprendre les enjeux de l’accompagnement : {sname}',f'Analyser le contexte, les acteurs, les objectifs et les contraintes propres à « {sname} ».',1,3,['CV','EXPERIENCE','MISSION','REFERENCE','ENTRETIEN','DOCUMENT'])
            addcrit(sc,'ACC_FACILITATION','ACCOMPAGNEMENT_COACHING','Faciliter les échanges et la construction collective','Créer un cadre de dialogue, faire émerger les contributions et soutenir une élaboration collective utile.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'ACC_MOBILISATION','ACCOMPAGNEMENT_COACHING','Mobiliser les acteurs et traiter les résistances avec discernement','Identifier adhésions, tensions et résistances, puis adapter l’intervention sans manipulation.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])
            addcrit(sc,'ACC_ACTION_SUIVI','METIER_TECHNIQUE','Transformer les échanges en décisions et actions suivies','Formaliser priorités, responsabilités, jalons et modalités de suivi adaptées.',1,3,['EXPERIENCE','MISSION','REFERENCE','DOCUMENT','ENTRETIEN'])
            addcrit(sc,'ACC_POSTURE','COMPORTEMENTAL','Tenir une posture neutre, claire et responsabilisante','Respecter les personnes, clarifier les rôles et favoriser leur autonomie dans les décisions.',1,3,['EXPERIENCE','MISSION','REFERENCE','ENTRETIEN'])

        for sc,ccode,cat,label,desc,required,minlevel,evidence_json,source_kind in criteria_seed:
            sr=c.execute(text('SELECT id FROM service_catalog WHERE service_code=:c'),{'c':sc}).mappings().first()
            if not sr: continue
            sid=sr['id']
            c.execute(text("""INSERT OR IGNORE INTO service_competency_criteria(
              service_id,criterion_code,category,label,description,required,minimum_level,accepted_evidence_json,active,current_version,source_kind,source_reference,created_at,updated_at)
              VALUES(:s,:c,:g,:l,:d,:r,:m,:e,1,1,:sk,'CDC correctif V1.1 / adaptation métier Clarté360 J15',:t,:t)"""),
              {'s':sid,'c':ccode,'g':cat,'l':label,'d':desc,'r':required,'m':minlevel,'e':evidence_json,'sk':source_kind,'t':j15_now})
            cr=c.execute(text('SELECT * FROM service_competency_criteria WHERE service_id=:s AND criterion_code=:c'),{'s':sid,'c':ccode}).mappings().first()
            if cr:
                c.execute(text("""INSERT OR IGNORE INTO service_criterion_versions(
                  criterion_id,service_id,version_no,criterion_code,category,label,description,required,weight,minimum_level,accepted_evidence_json,validity_months,active,source_kind,source_reference,change_reason,changed_by,created_at)
                  VALUES(:i,:s,1,:c,:g,:l,:d,:r,:w,:m,:e,:vm,1,:sk,:sr,'Initialisation critères J15','migration-j15',:t)"""),
                  {'i':cr['id'],'s':sid,'c':cr['criterion_code'],'g':cr['category'],'l':cr['label'],'d':cr.get('description'),'r':cr['required'],'w':cr.get('weight'),'m':cr['minimum_level'],'e':cr.get('accepted_evidence_json'),'vm':cr.get('validity_months'),'sk':cr.get('source_kind'),'sr':cr.get('source_reference'),'t':j15_now})

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
            "CREATE INDEX IF NOT EXISTS ix_action_tool_permissions_action ON action_tool_permissions(action_id,allowed,tool_id)",
            "CREATE INDEX IF NOT EXISTS ix_beneficiary_reports_action ON beneficiary_reports(action_id,status,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_prescription_tokens_expiry ON prescription_access_tokens(expires_at,revoked_at)",
            "CREATE INDEX IF NOT EXISTS ix_prescription_events_prescription ON prescription_events(prescription_id,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_prescription_documents_prescription ON prescription_documents(prescription_id,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_connector_cursors_updated ON connector_cursors(updated_at)",
            "CREATE INDEX IF NOT EXISTS ix_study_exports_date ON study_export_events(exported_at,actor)",
            "CREATE INDEX IF NOT EXISTS ix_crm_contacts_status ON crm_contacts(status,updated_at)",
            "CREATE INDEX IF NOT EXISTS ix_crm_contacts_email ON crm_contacts(email)",
            "CREATE INDEX IF NOT EXISTS ix_crm_contacts_beneficiary ON crm_contacts(beneficiary_id)",
            "CREATE INDEX IF NOT EXISTS ix_crm_tasks_contact_status ON crm_tasks(contact_id,status,due_at)",
            "CREATE INDEX IF NOT EXISTS ix_crm_action_links_contact ON crm_action_links(contact_id,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_crm_action_links_action ON crm_action_links(action_id,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_contractualization_action ON contractualization_cases(action_id,status,updated_at)",
            "CREATE INDEX IF NOT EXISTS ix_quality_events_status ON quality_events(status,severity,due_at)",
            "CREATE INDEX IF NOT EXISTS ix_quality_events_action ON quality_events(action_id,status,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_quality_review_points_status ON quality_review_points(status,action_id,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_service_catalog_active_name ON service_catalog(active,name)",
            "CREATE INDEX IF NOT EXISTS ix_service_catalog_family ON service_catalog(family,active)",
            "CREATE INDEX IF NOT EXISTS ix_service_versions_service ON service_versions(service_id,version_no)",
            "CREATE INDEX IF NOT EXISTS ix_service_criteria_service ON service_competency_criteria(service_id,active,category)",
            "CREATE INDEX IF NOT EXISTS ix_service_criterion_versions_criterion ON service_criterion_versions(criterion_id,version_no)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_trainers_professional_person_id ON trainers(professional_person_id) WHERE professional_person_id IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS ix_professional_persons_status ON professional_persons(principal_status,active,candidate_work_status)",
            "CREATE INDEX IF NOT EXISTS ix_professional_persons_supplier ON professional_persons(supplier_id)",
            "CREATE INDEX IF NOT EXISTS ix_professional_status_history_person ON professional_person_status_history(professional_person_id,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_professional_experiences_person ON professional_experiences(professional_person_id,start_date)",
            "CREATE INDEX IF NOT EXISTS ix_professional_education_person ON professional_education(professional_person_id,obtained_date)",
            "CREATE INDEX IF NOT EXISTS ix_professional_certifications_person ON professional_certifications(professional_person_id,valid_until)",
            "CREATE INDEX IF NOT EXISTS ix_professional_documents_person ON professional_documents(professional_person_id,category,valid_until)",
            "CREATE INDEX IF NOT EXISTS ix_professional_regulatory_nda ON professional_regulatory_status(nda_status,nda_number)",
            "CREATE INDEX IF NOT EXISTS ix_professional_regulatory_qualiopi ON professional_regulatory_status(qualiopi_status,qualiopi_valid_until)",
            "CREATE INDEX IF NOT EXISTS ix_person_service_qual_person ON person_service_qualifications(professional_person_id,service_id)",
            "CREATE INDEX IF NOT EXISTS ix_person_service_qual_review ON person_service_qualifications(review_due_at,human_value)",
            "CREATE INDEX IF NOT EXISTS ix_qual_criterion_person ON qualification_criterion_assessments(professional_person_id,service_id,criterion_id)",
            "CREATE INDEX IF NOT EXISTS ix_qualification_evidence_person ON qualification_evidence(professional_person_id,service_id,criterion_id)",
            "CREATE INDEX IF NOT EXISTS ix_qualification_history_person ON qualification_history(professional_person_id,service_id,created_at)",
            "CREATE INDEX IF NOT EXISTS ix_prof_maintenance_person_key ON professional_maintenance_actions(professional_person_id,alert_key,created_at)",
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
