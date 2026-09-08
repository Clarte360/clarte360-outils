from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from db import make_engine, init_db, one, q, execute, utcnow_iso
from services import (
    create_action, add_participant, add_slot, add_trainer, assign_trainer,
    assign_slot_trainer, set_attendance_status, countersign_slot,
    slot_countersignature_eligibility, list_slot_countersignatures,
    required_slot_countersignatures_complete, ensure_tokens_and_events,
    safe_update_slot, report_slot,
)


def seed(no='V3I3-001', slot_date='2026-09-04', start='09:00', end='12:00'):
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=create_action(e,{
        'action_no':no,'title':'I3','subtitle':None,'nature':'FORMATION','mode':'PRESENTIEL',
        'client_name':'Client','client_type':'Entreprise','group_code':None,'planned_hours':3,
        'expected_participants':2,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Paris','notes':None,'source':'TEST'
    },'test')
    t1=add_trainer(e,'Intervenant Un','one@example.org','','test'); assign_trainer(e,aid,t1,'test')
    p1,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'a@example.org'},'test')
    p2,_=add_participant(e,aid,{'last_name':'MARTIN','first_name':'Paul','birth_date':'1991-01-01','email':'p@example.org'},'test')
    sid=add_slot(e,aid,slot_date,start,end,'test')
    return e,aid,t1,p1,p2,sid


def finalized(e,p1,p2,sid):
    set_attendance_status(e,p1,sid,'ABSENT','malade','test')
    set_attendance_status(e,p2,sid,'NON_CONCERNE','non prévu','test')


def test_i3_future_slot_is_blocked_server_side_even_with_signature_bytes():
    e,aid,t1,p1,p2,sid=seed(slot_date='2026-09-10')
    finalized(e,p1,p2,sid)
    now=datetime(2026,9,5,10,0,tzinfo=ZoneInfo('Europe/Paris'))
    ok,msg,_=slot_countersignature_eligibility(e,sid,t1,now=now)
    assert not ok and 'avant la fin réelle' in msg
    ok,msg=countersign_slot(e,sid,'Intervenant Un','one@example.org','trainer','certifie',trainer_id=t1,signature_bytes=b'png',now=now)
    assert not ok and 'avant la fin réelle' in msg
    assert not list_slot_countersignatures(e,sid)


def test_i3_pending_participant_blocks_countersignature():
    e,aid,t1,p1,p2,sid=seed()
    set_attendance_status(e,p1,sid,'ABSENT','malade','test')
    now=datetime(2026,9,5,10,0,tzinfo=ZoneInfo('Europe/Paris'))
    ok,msg,_=slot_countersignature_eligibility(e,sid,t1,now=now)
    assert not ok and 'Paul MARTIN' in msg


def test_i3_coanimation_requires_one_immutable_signature_per_active_trainer(tmp_path, monkeypatch):
    e,aid,t1,p1,p2,sid=seed(no='V3I3-CO')
    t2=add_trainer(e,'Intervenant Deux','two@example.org','','test')
    assign_slot_trainer(e,sid,t2,'test','CO_INTERVENANT')
    finalized(e,p1,p2,sid)
    now=datetime(2026,9,5,10,0,tzinfo=ZoneInfo('Europe/Paris'))
    ok,msg=countersign_slot(e,sid,'Intervenant Un','one@example.org','trainer:1','certifie',trainer_id=t1,signature_bytes=b'png-one',now=now)
    assert ok,msg
    complete,missing=required_slot_countersignatures_complete(e,sid)
    assert not complete and [x['trainer_id'] for x in missing]==[t2]
    ok,msg=countersign_slot(e,sid,'Intervenant Deux','two@example.org','trainer:2','certifie',trainer_id=t2,signature_bytes=b'png-two',now=now)
    assert ok,msg
    assert required_slot_countersignatures_complete(e,sid)[0]
    assert len(list_slot_countersignatures(e,sid))==2
    ok,msg=countersign_slot(e,sid,'Intervenant Un','one@example.org','trainer:1','modification',trainer_id=t1,signature_bytes=b'changed',now=now)
    assert not ok and 'déjà enregistrée' in msg


def test_i3_only_one_automatic_attendance_email_and_old_pending_reminders_are_skipped():
    e,aid,t1,p1,p2,sid=seed(no='V3I3-MAIL')
    execute(e,"INSERT INTO email_events(participant_id,slot_id,event_type,due_at,status) VALUES(:p,:s,'RELANCE_1',:d,'PENDING')",{'p':p1,'s':sid,'d':utcnow_iso()})
    ensure_tokens_and_events(e,aid,'https://example.org','Europe/Paris')
    rows=q(e,'SELECT participant_id,event_type,status,due_at FROM email_events WHERE slot_id=:s ORDER BY participant_id,event_type',{'s':sid})
    assert all(r['event_type']=='INITIAL' or r['status']=='SKIPPED' for r in rows)
    assert one(e,"SELECT COUNT(*) n FROM email_events WHERE slot_id=:s AND event_type='INITIAL'",{'s':sid})['n']==2
    assert one(e,"SELECT COUNT(*) n FROM email_events WHERE slot_id=:s AND event_type IN ('RELANCE_1','RELANCE_2') AND status='PENDING'",{'s':sid})['n']==0
    initial=one(e,"SELECT due_at FROM email_events WHERE participant_id=:p AND slot_id=:s AND event_type='INITIAL'",{'p':p1,'s':sid})['due_at']
    assert initial=='2026-09-04T07:00:00+00:00'


def test_i3_countersignature_is_historical_evidence_locking_rewrite_and_report():
    e,aid,t1,p1,p2,sid=seed(no='V3I3-LOCK')
    finalized(e,p1,p2,sid)
    now=datetime(2026,9,5,10,0,tzinfo=ZoneInfo('Europe/Paris'))
    ok,msg=countersign_slot(e,sid,'Intervenant Un','one@example.org','trainer','certifie',trainer_id=t1,signature_bytes=b'png',now=now); assert ok,msg
    ok,msg=safe_update_slot(e,sid,{'slot_date':'2026-09-04','start_time':'10:00','end_time':'13:00','send_offset_min':-10,'reminder1_offset_min':20,'reminder2_offset_min':120,'close_offset_min':1440},'admin')
    assert not ok and 'preuve' in msg
    assert report_slot(e,sid,'2026-09-06','10:00','13:00','admin','test') is None


def test_i3_overnight_end_time_blocks_until_next_day_end():
    e,aid,t1,p1,p2,sid=seed(no='V3I3-NIGHT',slot_date='2026-09-04',start='23:00',end='01:00')
    finalized(e,p1,p2,sid)
    before=datetime(2026,9,5,0,30,tzinfo=ZoneInfo('Europe/Paris'))
    after=datetime(2026,9,5,1,1,tzinfo=ZoneInfo('Europe/Paris'))
    assert not slot_countersignature_eligibility(e,sid,t1,now=before)[0]
    assert slot_countersignature_eligibility(e,sid,t1,now=after)[0]


def test_i3_legacy_countersignature_is_copied_additively_on_init_db():
    e,aid,t1,p1,p2,sid=seed(no='V3I3-MIG')
    execute(e,"""INSERT INTO trainer_countersignatures(slot_id,trainer_name,trainer_email,signed_at,declaration_text,method,actor)
      VALUES(:s,'Intervenant Un','one@example.org',:n,'historique','NOM_PRENOM','legacy')""",{'s':sid,'n':utcnow_iso()})
    legacy=one(e,'SELECT * FROM trainer_countersignatures WHERE slot_id=:s',{'s':sid})
    init_db(e)
    migrated=one(e,'SELECT * FROM trainer_countersignatures_v3 WHERE legacy_source_id=:i',{'i':legacy['id']})
    assert migrated and migrated['slot_id']==sid and migrated['trainer_id']==t1
    assert one(e,'SELECT COUNT(*) n FROM trainer_countersignatures WHERE id=:i',{'i':legacy['id']})['n']==1
    init_db(e)
    assert one(e,'SELECT COUNT(*) n FROM trainer_countersignatures_v3 WHERE legacy_source_id=:i',{'i':legacy['id']})['n']==1
