from datetime import datetime, timedelta, timezone
from pathlib import Path

from db import make_engine, init_db, one, execute, utcnow_iso
from persistent_session import create_session, resolve_session, revoke_session, revoke_subject_sessions
from ui_guard import safe_call, user_message
from services import create_action, add_participant, add_slot, set_attendance_status
from pdf_utils import individual_pdf


def memory_engine():
    e = make_engine('sqlite:///:memory:')
    init_db(e)
    return e


def test_i9a_auth_session_is_persistent_hashed_and_revocable():
    e = memory_engine()
    token = create_session(e, 'ADMIN', 'admin@example.org', ttl_hours=12, ip_address='127.0.0.1', user_agent='pytest')
    assert token and len(token) > 30
    row = one(e, 'SELECT * FROM auth_sessions')
    assert row['token_hash'] != token
    assert token not in str(row)
    restored = resolve_session(e, token, expected_type='ADMIN')
    assert restored and restored['subject_ref'] == 'admin@example.org'
    assert resolve_session(e, token, expected_type='TRAINER') is None
    revoke_session(e, token)
    assert resolve_session(e, token, expected_type='ADMIN') is None


def test_i9a_auth_session_expiry_and_subject_revoke():
    e = memory_engine()
    t1 = create_session(e, 'TRAINER', 7, ttl_hours=1)
    t2 = create_session(e, 'TRAINER', 7, ttl_hours=1)
    execute(e, 'UPDATE auth_sessions SET expires_at=:x WHERE token_hash=(SELECT token_hash FROM auth_sessions ORDER BY id LIMIT 1)', {
        'x': (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    })
    assert resolve_session(e, t1, expected_type='TRAINER') is None
    assert resolve_session(e, t2, expected_type='TRAINER') is not None
    assert revoke_subject_sessions(e, 'TRAINER', 7) >= 1
    assert resolve_session(e, t2, expected_type='TRAINER') is None


def test_i9a_init_db_migration_is_additive_and_idempotent():
    e = memory_engine()
    execute(e, "INSERT INTO admins(email,password_hash,full_name,created_at) VALUES('a@b.c','hash','Admin',:n)", {'n': utcnow_iso()})
    init_db(e)
    init_db(e)
    assert one(e, "SELECT email FROM admins WHERE email='a@b.c'")['email'] == 'a@b.c'
    assert one(e, "SELECT name FROM sqlite_master WHERE type='table' AND name='auth_sessions'")


def test_i9a_ui_error_is_logged_and_user_message_is_non_technical():
    e = memory_engine()
    ok, value, ref = safe_call(e, 'pdf_test', lambda: (_ for _ in ()).throw(AttributeError("'str' object has no attribute 'wrapOn'")))
    assert not ok and value is None and ref
    log = one(e, "SELECT * FROM audit_log WHERE event_type='UI_MODULE_ERROR'")
    assert log and ref in log['details_json'] and 'wrapOn' in log['details_json']
    msg = user_message(ref, subject='Le document')
    assert 'wrapOn' not in msg and 'Traceback' not in msg and ref in msg


def test_i9a_individual_pdf_accepts_missing_signature_image_without_wrapon():
    e = memory_engine()
    aid = create_action(e, {
        'action_no':'I9A-PDF','title':'Test PDF','subtitle':None,'nature':'FORMATION','mode':'PRESENTIEL',
        'client_name':'Client','client_type':'Entreprise','group_code':None,'planned_hours':1,
        'expected_participants':1,'admin_email':'admin@example.org','trainer_name':'Intervenant','trainer_email':'trainer@example.org',
        'location':'Paris','notes':None,'source':'TEST'
    }, 'test')
    pid, _ = add_participant(e, aid, {'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'a@example.org'}, 'test')
    sid = add_slot(e, aid, '2026-09-01', '09:00', '10:00', 'test')
    set_attendance_status(e, pid, sid, 'ABSENT', 'test', 'test')
    execute(e, """INSERT INTO trainer_countersignatures_v3(
        slot_id,trainer_id,trainer_name,trainer_email,signed_at,declaration_text,signature_path,signature_sha256,method,actor,created_at
        ) VALUES(:s,NULL,'Intervenant','trainer@example.org',:n,'certifie',NULL,NULL,'NOM_PRENOM','test',:n)""", {'s':sid,'n':utcnow_iso()})
    data = individual_pdf(e, pid)
    assert data.startswith(b'%PDF') and len(data) > 1000


def test_i9a_source_uses_module_guard_and_never_exposes_raw_pdf_exception():
    src = Path('app.py').read_text(encoding='utf-8')
    assert "_run_ui_module('dashboard'" in src
    assert 'PDF indisponible : {ex}' not in src
    assert 'st.exception(' not in src
