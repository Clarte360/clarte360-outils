from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from db import make_engine, init_db, execute, q, one
from services import create_action, add_participant, add_slot, add_trainer, assign_trainer, refresh_countersign_communications

ROOT=Path(__file__).resolve().parents[1]


def _seed():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=create_action(e,{
        'action_no':'H27-001','title':'H27','nature':'Formation','mode':'INDIVIDUEL','delivery_mode':'DISTANCIEL_VISIO',
        'client_name':None,'client_type':'Particulier','planned_hours':2,'expected_participants':1,
        'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,'group_code':None,'notes':None,'subtitle':None,'location':'Online','source':'TEST'
    },'test')
    pid,_=add_participant(e,aid,{'last_name':'DOE','first_name':'Jane','birth_date':'1990-01-01','email':'jane@example.com'},'test')
    tid=add_trainer(e,'Trainer','trainer@example.com','','test'); assign_trainer(e,aid,tid,'test')
    sid=add_slot(e,aid,'2026-09-15','19:30','21:30','test')
    execute(e,"UPDATE actions SET status='ACTIVE' WHERE id=:a",{'a':aid})
    return e,aid,pid,tid,sid


def test_no_future_countersign_request_with_pending_participant():
    e,aid,pid,tid,sid=_seed()
    refresh_countersign_communications(e,now=datetime(2026,9,15,18,0,tzinfo=ZoneInfo('Europe/Paris')))
    assert not q(e,"SELECT * FROM communication_events WHERE communication_type='COUNTERSIGN_REQUEST' AND status<>'ANNULE'")


def test_request_created_at_end_even_if_participant_pending():
    e,aid,pid,tid,sid=_seed()
    refresh_countersign_communications(e,now=datetime(2026,9,15,21,31,tzinfo=ZoneInfo('Europe/Paris')))
    rows=q(e,"SELECT * FROM communication_events WHERE communication_type='COUNTERSIGN_REQUEST'")
    assert len(rows)==1 and rows[0]['slot_id']==sid and rows[0]['status']=='A_ENVOYER'


def test_future_stale_request_is_cancelled():
    e,aid,pid,tid,sid=_seed()
    execute(e,"INSERT INTO communication_events(action_id,trainer_id,slot_id,communication_type,recipient_email,trigger_mode,status,due_at,idempotency_key,created_at,updated_at) VALUES(:a,:t,:s,'COUNTERSIGN_REQUEST','trainer@example.com','AUTO','A_ENVOYER','2026-09-15T19:30:00+00:00',:k,'2026-09-01','2026-09-01')",{'a':aid,'t':tid,'s':sid,'k':f'countersign:{sid}:{tid}'})
    refresh_countersign_communications(e,now=datetime(2026,9,15,18,0,tzinfo=ZoneInfo('Europe/Paris')))
    row=one(e,"SELECT * FROM communication_events WHERE slot_id=:s AND communication_type='COUNTERSIGN_REQUEST'",{'s':sid})
    assert row['status']=='ANNULE'


def test_tracking_uses_datetime_time_alias_only():
    src=(ROOT/'app.py').read_text(encoding='utf-8')
    assert "value=time(12,0)" not in src
    assert "value=dt_time(12,0)" in src


def test_future_teams_copy_is_planned_not_missing_report():
    src=(ROOT/'app.py').read_text(encoding='utf-8')
    assert 'réunion planifiée. Le rapport Microsoft sera recherché automatiquement après la séance.' in src
