from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from db import make_engine, init_db, one, q, execute
from services import (
    create_action, add_participant, add_slot, add_trainer, assign_trainer,
    assign_action_trainer, assign_slot_trainer,
    set_action_trainer_planning_permission, set_slot_trainer_planning_permission,
    trainer_planning_scope, validate_trainer_planning_change,
    trainer_update_slot, trainer_add_slot, action_calendar_ics,
    ensure_tokens_and_events,
)


def seed(no='V3I4-001'):
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=create_action(e,{
        'action_no':no,'title':'Action I4','subtitle':None,'nature':'FORMATION','mode':'INDIVIDUEL',
        'client_name':'Client','client_type':'Entreprise','group_code':None,'planned_hours':6,
        'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Paris','notes':None,'source':'TEST'
    },'test')
    execute(e,"UPDATE actions SET start_date='2026-09-10',end_date='2026-09-30' WHERE id=:a",{'a':aid})
    t1=add_trainer(e,'Référent','ref@example.org','','test'); assign_trainer(e,aid,t1,'test')
    p1,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'anne@example.org'},'test')
    s1=add_slot(e,aid,'2026-09-15','09:00','12:00','test')
    s2=add_slot(e,aid,'2026-09-20','09:00','12:00','test')
    return e,aid,t1,p1,s1,s2


def test_i4_planning_permissions_are_explicit_and_additive():
    e,aid,t1,p1,s1,s2=seed()
    assert trainer_planning_scope(e,t1,aid)['can_manage_action'] is False
    ok,msg=set_action_trainer_planning_permission(e,aid,t1,True,'admin'); assert ok,msg
    assert trainer_planning_scope(e,t1,aid)['can_manage_action'] is True
    cols={x['name'] for x in q(e,'PRAGMA table_info(action_trainers)')}
    assert 'can_manage_planning' in cols
    cols2={x['name'] for x in q(e,'PRAGMA table_info(slot_trainers)')}
    assert 'can_manage_planning' in cols2
    assert one(e,"SELECT name FROM sqlite_master WHERE type='table' AND name='planning_change_events'")


def test_i4_slot_permission_allows_only_own_slot_and_coanimation_needs_action_right():
    e,aid,t1,p1,s1,s2=seed('V3I4-SLOT')
    t2=add_trainer(e,'Ponctuel','p@example.org','','test')
    assign_slot_trainer(e,s2,t2,'admin','CO_INTERVENANT')
    ok,msg=set_slot_trainer_planning_permission(e,s2,t2,True,'admin'); assert ok,msg
    now=datetime(2026,9,5,10,0,tzinfo=ZoneInfo('Europe/Paris'))
    ok,msg,_=validate_trainer_planning_change(e,t2,aid,slot_id=s1,date_s='2026-09-16',start_s='09:00',end_s='12:00',now=now)
    assert not ok and 'autorisé' in msg
    ok,msg,_=validate_trainer_planning_change(e,t2,aid,slot_id=s2,date_s='2026-09-21',start_s='09:00',end_s='12:00',now=now)
    assert not ok and 'autre intervenant' in msg
    ok,msg=set_action_trainer_planning_permission(e,aid,t2,True,'admin')
    assert not ok  # punctual slot assignment alone is not action membership
    ok,msg=assign_action_trainer(e,aid,t2,'admin','INTERVENANT',False); assert ok,msg
    ok,msg=set_action_trainer_planning_permission(e,aid,t2,True,'admin'); assert ok,msg
    ok,msg,_=validate_trainer_planning_change(e,t2,aid,slot_id=s2,date_s='2026-09-21',start_s='09:00',end_s='12:00',now=now)
    assert ok,msg


def test_i4_update_preserves_duration_reschedules_attendance_and_logs_propagation():
    e,aid,t1,p1,s1,s2=seed('V3I4-SYNC')
    set_action_trainer_planning_permission(e,aid,t1,True,'admin')
    ensure_tokens_and_events(e,aid,'https://example.org')
    before=one(e,"SELECT due_at FROM email_events WHERE participant_id=:p AND slot_id=:s AND event_type='INITIAL'",{'p':p1,'s':s1})['due_at']
    now=datetime(2026,9,5,10,0,tzinfo=ZoneInfo('Europe/Paris'))
    ok,msg=trainer_update_slot(e,t1,s1,'2026-09-16','10:00','13:00','trainer:1',base_url='https://example.org',now=now)
    assert ok,msg
    after=one(e,"SELECT due_at FROM email_events WHERE participant_id=:p AND slot_id=:s AND event_type='INITIAL'",{'p':p1,'s':s1})['due_at']
    assert after != before and after=='2026-09-16T08:00:00+00:00'
    ev=one(e,"SELECT * FROM planning_change_events WHERE slot_id=:s ORDER BY id DESC LIMIT 1",{'s':s1})
    assert ev and ev['attendance_synced']==1 and ev['portals_synced']==1 and ev['teams_status']=='NOT_ENABLED'


def test_i4_guardrails_block_volume_change_bounds_overlap_and_past_changes():
    e,aid,t1,p1,s1,s2=seed('V3I4-GUARD')
    set_action_trainer_planning_permission(e,aid,t1,True,'admin')
    now=datetime(2026,9,5,10,0,tzinfo=ZoneInfo('Europe/Paris'))
    ok,msg,_=validate_trainer_planning_change(e,t1,aid,slot_id=s1,date_s='2026-09-16',start_s='09:00',end_s='13:00',now=now)
    assert not ok and 'volume horaire' in msg
    ok,msg,_=validate_trainer_planning_change(e,t1,aid,slot_id=s1,date_s='2026-10-01',start_s='09:00',end_s='12:00',now=now)
    assert not ok and "date de fin" in msg
    ok,msg,_=validate_trainer_planning_change(e,t1,aid,slot_id=s1,date_s='2026-09-20',start_s='10:00',end_s='13:00',now=now)
    assert not ok and 'Chevauchement' in msg
    late=datetime(2026,9,16,10,0,tzinfo=ZoneInfo('Europe/Paris'))
    ok,msg,_=validate_trainer_planning_change(e,t1,aid,slot_id=s1,date_s='2026-09-17',start_s='09:00',end_s='12:00',now=late)
    assert not ok and 'déjà terminée' in msg


def test_i4_authorized_trainer_can_add_only_without_exceeding_contractual_hours():
    e,aid,t1,p1,s1,s2=seed('V3I4-ADD')
    set_action_trainer_planning_permission(e,aid,t1,True,'admin')
    now=datetime(2026,9,5,10,0,tzinfo=ZoneInfo('Europe/Paris'))
    sid,msg=trainer_add_slot(e,t1,aid,'2026-09-25','09:00','10:00','trainer:1',now=now)
    assert sid is None and 'contractuelles' in msg  # already 6h / 6h
    execute(e,'UPDATE actions SET planned_hours=7 WHERE id=:a',{'a':aid})
    sid,msg=trainer_add_slot(e,t1,aid,'2026-09-25','09:00','10:00','trainer:1',now=now)
    assert sid and not msg


def test_i4_ics_uses_stable_slot_uid_and_marks_reported_occurrence_cancelled():
    e,aid,t1,p1,s1,s2=seed('V3I4-ICS')
    raw=action_calendar_ics(e,aid,trainer_id=t1).decode('utf-8')
    assert f'UID:clarte360-slot-{s1}@gestion-actions' in raw
    assert 'DTSTART;TZID=Europe/Paris:20260915T090000' in raw
    execute(e,"UPDATE slots SET status='REPORTE' WHERE id=:s",{'s':s1})
    raw2=action_calendar_ics(e,aid,trainer_id=t1).decode('utf-8')
    assert f'UID:clarte360-slot-{s1}@gestion-actions' in raw2 and 'STATUS:CANCELLED' in raw2


def test_i4_admin_login_no_longer_exposes_other_portal_buttons():
    txt=Path('app.py').read_text(encoding='utf-8')
    start=txt.index('def setup_or_login():')
    end=txt.index('def signature_page',start)
    block=txt[start:end]
    assert 'Clarté360 — Gestion des actions — Administration' in block
    assert "Accès formateur / accompagnant" not in block
    assert "Accès stagiaire / bénéficiaire" not in block
    assert '?trainer_portal=1' not in block and '?beneficiary_portal=1' not in block
