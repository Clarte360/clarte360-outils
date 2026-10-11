"""J10-R27: isolated, deterministic SQLite tests; SMTP is always replaced by a stub."""
from datetime import datetime as RealDateTime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import worker
from db import make_engine, init_db, execute, one, q, utcnow_iso
from services import (
    create_action, add_participant, add_slot, add_trainer, assign_trainer,
    ensure_tokens_and_events, ensure_default_organization, report_slot,
    update_slot, synchronize_teams_reminders, teams_reminder_event_state,
    refresh_all_worker_events, set_generic_action_module, list_slot_trainers,
    unassign_slot_trainer, assign_slot_trainer,
)

PARIS=ZoneInfo('Europe/Paris')
START=RealDateTime(2030, 6, 10, 12, 0, tzinfo=PARIS)  # 10:00 UTC
H15=RealDateTime(2030, 6, 10, 9, 45, tzinfo=timezone.utc)
H2=RealDateTime(2030, 6, 10, 8, 0, tzinfo=timezone.utc)


def seed(tmp_path, *, trainer=False):
    e=make_engine('sqlite:///'+str(tmp_path/'r27_autonomous.db'))
    init_db(e);ensure_default_organization(e)
    aid=create_action(e,dict(action_no='R27-TEST',title='Formation de recette fictive',subtitle=None,
        nature='FORMATION',mode='DISTANCIEL',client_name='Entreprise fictive',client_type='Entreprise',
        group_code=None,planned_hours=1,expected_participants=1,admin_email='admin@example.invalid',
        trainer_name=None,trainer_email=None,location='En ligne',notes=None,source='TEST_R27'),'test')
    execute(e,"UPDATE actions SET status='ACTIVE' WHERE id=:a",{'a':aid})
    execute(e,"""INSERT INTO action_modules(action_id,module_code,enabled,enabled_at,enabled_by,created_at,updated_at)
       VALUES(:a,'TEAMS',1,:t,'test',:t,:t)""",{'a':aid,'t':utcnow_iso()})
    tid=None
    if trainer:
        tid=add_trainer(e,'Formateur fictif','trainer@example.invalid','','test')
        assign_trainer(e,aid,tid,'test')
    pid,_=add_participant(e,aid,{'last_name':'FICTIF','first_name':'Participant',
         'birth_date':'1990-01-01','email':'person@example.invalid'},'test')
    sid=add_slot(e,aid,START.date().isoformat(),START.strftime('%H:%M'),(START+timedelta(hours=1)).strftime('%H:%M'),'test')
    return e,aid,pid,sid,tid


def reminders(e,sid=None):
    sql="SELECT * FROM communication_events WHERE communication_type IN ('TEAMS_REMINDER_H2','TEAMS_REMINDER_H15')"
    if sid is not None:sql+=' AND slot_id=:s'
    return q(e,sql+' ORDER BY id',{'s':sid} if sid is not None else {})


def clock_worker(monkeypatch,when):
    class FakeDateTime(RealDateTime):
        @classmethod
        def now(cls,tz=None):
            return when.astimezone(tz) if tz is not None else when.replace(tzinfo=None)
    monkeypatch.setattr(worker,'datetime',FakeDateTime)


def test_manual_between_h2_and_h15_never_delivers_stale_h2(tmp_path,monkeypatch):
    e,aid,pid,sid,tid=seed(tmp_path)
    results=synchronize_teams_reminders(e,now=RealDateTime(2030,6,10,9,30,tzinfo=timezone.utc))
    h2=one(e,"SELECT * FROM communication_events WHERE slot_id=:s AND communication_type='TEAMS_REMINDER_H2'",{'s':sid})
    h15=one(e,"SELECT * FROM communication_events WHERE slot_id=:s AND communication_type='TEAMS_REMINDER_H15'",{'s':sid})
    assert h2['status']=='ANNULE' and 'REMINDER_EXPIRED' in h2['last_error']
    assert h15['status']=='A_ENVOYER'
    clock_worker(monkeypatch,H15)
    sent=[]
    monkeypatch.setattr(worker,'send_mail',lambda cfg,to,subject,html:sent.append((to,subject,html)))
    worker._run_communication_events(e,{'enabled':True},'https://example.invalid')
    assert len([x for x in sent if 'Rappel séance dans 15 minutes' in x[1]])==1
    assert not [x for x in sent if 'Rappel séance dans 2 heures' in x[1]]
    assert one(e,'SELECT status FROM communication_events WHERE id=:i',{'i':h15['id']})['status']=='ENVOYE'


def test_repeated_manual_refresh_never_resends_sent_messages(tmp_path,monkeypatch):
    e,aid,pid,sid,tid=seed(tmp_path)
    clock_worker(monkeypatch,H15)
    sent=[]
    monkeypatch.setattr(worker,'send_mail',lambda cfg,to,subject,html:sent.append(subject))
    synchronize_teams_reminders(e,now=H15)
    worker._run_communication_events(e,{},'https://example.invalid')
    first=len(sent)
    assert any('15 minutes' in x for x in sent)
    for _ in range(3):
        synchronize_teams_reminders(e,now=H15)
        refresh_all_worker_events(e,'https://example.invalid','Europe/Paris','admin')
        worker._run_communication_events(e,{},'https://example.invalid')
    assert len(sent)==first
    assert sum(r['status']=='ENVOYE' for r in reminders(e,sid))==1


def test_report_cancels_attendance_pending_keeps_sent_evidence(tmp_path):
    e,aid,pid,sid,tid=seed(tmp_path)
    ensure_tokens_and_events(e,aid,'https://example.invalid')
    before=reminders(e,sid)
    assert before
    execute(e,"UPDATE communication_events SET status='ENVOYE',sent_at='2030-01-01T00:00:00+00:00' WHERE id=:i",{'i':before[0]['id']})
    new=report_slot(e,sid,'2030-06-12','12:00','13:00','admin','Déplacement')
    assert new is not None and new!=sid
    assert all(r['status']!='A_ENVOYER' for r in reminders(e,sid))
    assert one(e,'SELECT status FROM communication_events WHERE id=:i',{'i':before[0]['id']})['status']=='ENVOYE'
    assert one(e,"SELECT status FROM email_events WHERE slot_id=:s AND event_type='INITIAL'",{'s':sid})['status']=='SKIPPED'
    assert one(e,'SELECT status FROM slots WHERE id=:s',{'s':sid})['status']=='REPORTE'
    assert any(r['status']=='A_ENVOYER' for r in reminders(e,new))


def test_same_slot_change_preserves_attendance_and_reprograms_due(tmp_path):
    e,aid,pid,sid,tid=seed(tmp_path)
    ensure_tokens_and_events(e,aid,'https://example.invalid')
    old=one(e,"SELECT * FROM email_events WHERE slot_id=:s AND event_type='INITIAL'",{'s':sid})
    update_slot(e,sid,{'slot_date':'2030-06-11','start_time':'14:00','end_time':'15:00',
        'send_offset_min':-10,'reminder1_offset_min':20,'reminder2_offset_min':120,'close_offset_min':1440},'admin')
    new=one(e,"SELECT * FROM email_events WHERE slot_id=:s AND event_type='INITIAL'",{'s':sid})
    assert new['id']==old['id'] and new['status']=='PENDING' and new['due_at']!=old['due_at']
    assert any(r['status']=='ANNULE' for r in reminders(e,sid))
    assert any(r['status']=='A_ENVOYER' and r['due_at'].startswith('2030-06-11') for r in reminders(e,sid))


def test_revoke_participant_before_smtp_blocks_message(tmp_path,monkeypatch):
    e,aid,pid,sid,tid=seed(tmp_path)
    clock_worker(monkeypatch,H15)
    execute(e,'UPDATE participants SET active=0 WHERE id=:p',{'p':pid})
    sent=[]
    monkeypatch.setattr(worker,'send_mail',lambda *x:sent.append(x))
    worker._run_communication_events(e,{},'https://example.invalid')
    assert not sent or not any('Rappel séance' in x[2] for x in sent)
    assert not any(r['status']=='ENVOYE' for r in reminders(e,sid))
    assert synchronize_teams_reminders(e,now=H15)['pending']==0


def test_reported_reminder_requeued_by_legacy_is_caught_before_smtp(tmp_path,monkeypatch):
    e,aid,pid,sid,tid=seed(tmp_path)
    report_slot(e,sid,'2030-06-11','12:00','13:00','admin','Report fictif')
    ev=one(e,"SELECT id FROM communication_events WHERE slot_id=:s AND communication_type='TEAMS_REMINDER_H15'",{'s':sid})
    execute(e,"UPDATE communication_events SET status='A_ENVOYER',due_at='2000-01-01T00:00:00+00:00' WHERE id=:id",{'id':ev['id']})
    clock_worker(monkeypatch,H15)
    sent=[]
    monkeypatch.setattr(worker,'send_mail',lambda *x:sent.append(x))
    worker._run_communication_events(e,{},'https://example.invalid')
    assert not any('Rappel séance' in x[2] for x in sent)
    assert one(e,'SELECT status FROM communication_events WHERE id=:i',{'i':ev['id']})['status']=='ANNULE'


def test_disabled_teams_cancels_previously_scheduled(tmp_path):
    e,aid,pid,sid,tid=seed(tmp_path)
    set_generic_action_module(e,aid,'TEAMS',False,'admin')
    assert all(x['status']=='ANNULE' for x in reminders(e,sid))
    assert synchronize_teams_reminders(e,now=H15)['prepared']==0


def test_trainer_removed_from_slot_never_gets_reminder(tmp_path,monkeypatch):
    e,aid,pid,sid,tid=seed(tmp_path,trainer=True)
    assert list_slot_trainers(e,sid)
    ok,msg=unassign_slot_trainer(e,sid,tid,'admin','Absent')
    assert ok,msg
    clock_worker(monkeypatch,H15)
    sent=[]
    monkeypatch.setattr(worker,'send_mail',lambda c,to,s,b:sent.append(to))
    worker._run_communication_events(e,{},'https://example.invalid')
    assert 'trainer@example.invalid' not in sent
    synchronize_teams_reminders(e,now=H15)
    assert not any(r['trainer_id']==tid and r['status']=='A_ENVOYER' for r in reminders(e,sid))


def test_smtp_failure_keeps_trace_and_does_not_blindly_retry(tmp_path,monkeypatch):
    e,aid,pid,sid,tid=seed(tmp_path)
    clock_worker(monkeypatch,H15)
    def fail(*args):raise ConnectionError('Simulated SMTP failure')
    monkeypatch.setattr(worker,'send_mail',fail)
    worker._run_communication_events(e,{},'https://example.invalid')
    fail_ev=one(e,"SELECT * FROM communication_events WHERE slot_id=:s AND communication_type='TEAMS_REMINDER_H15'",{'s':sid})
    assert fail_ev['status']=='ECHEC' and 'Simulated' in fail_ev['last_error']
    synchronize_teams_reminders(e,now=H15)
    assert one(e,'SELECT status FROM communication_events WHERE id=:i',{'i':fail_ev['id']})['status']=='ECHEC'
    assert len([r for r in reminders(e,sid) if r['communication_type']=='TEAMS_REMINDER_H15'])==1


def test_duplicate_manual_refresh_and_worker_use_same_queue(tmp_path):
    e,aid,pid,sid,tid=seed(tmp_path)
    original=len(reminders(e,sid))
    for _ in range(4):
        refresh_all_worker_events(e,'https://example.invalid')
        synchronize_teams_reminders(e)
    assert len(reminders(e,sid))==original


def test_worker_background_prepares_without_manual_click_even_smtp_off(tmp_path,monkeypatch):
    e,aid,pid,sid,tid=seed(tmp_path)
    # Simulate an old installation without queued reminders, then let the worker run.
    execute(e,"DELETE FROM communication_events WHERE communication_type IN ('TEAMS_REMINDER_H2','TEAMS_REMINDER_H15')")
    for name in ('_run_crm_callback_notifications','_quarantine_stale_sending','_quarantine_stale_quality',
                 '_quarantine_stale_client_transmissions','generate_due_final_bundles','_process_teams',
                 'refresh_pip_connector_runtime_status','refresh_ipip_connector_runtime_status','refresh_countersign_communications'):
        monkeypatch.setattr(worker,name,lambda *a,**k:0)
    monkeypatch.setattr(worker,'load_cfg',lambda:{'database':{'url':'sqlite:///:memory:'},'app':{'base_url':'https://example.invalid'}})
    monkeypatch.setattr(worker,'make_engine',lambda _:e)
    monkeypatch.setattr(worker,'init_db',lambda _:None)
    clock_worker(monkeypatch,RealDateTime(2030,6,10,7,30,tzinfo=timezone.utc))
    assert worker.run_once()==0
    assert len(reminders(e,sid))==2


def test_reminder_timezone_uses_real_utc_and_organization_zone(tmp_path):
    e,aid,pid,sid,tid=seed(tmp_path)
    r=one(e,"SELECT * FROM communication_events WHERE slot_id=:s AND communication_type='TEAMS_REMINDER_H2'",{'s':sid})
    assert r['due_at']==H2.isoformat()
    ok,_,_=teams_reminder_event_state(e,r,now=H2)
    assert ok
    # Budapest and Paris use the same summer offset; New York is the genuine comparison.
    org=one(e,'SELECT id FROM organizations ORDER BY id LIMIT 1')
    execute(e,"UPDATE organizations SET timezone='Europe/Budapest' WHERE id=:o",{'o':org['id']})
    assert synchronize_teams_reminders(e,now=RealDateTime(2029,1,1,tzinfo=timezone.utc))['prepared']==0
    execute(e,"UPDATE organizations SET timezone='America/New_York' WHERE id=:o",{'o':org['id']})
    r2=synchronize_teams_reminders(e,now=RealDateTime(2029,1,1,tzinfo=timezone.utc))
    assert r2['prepared']>=1
    assert any(x['status']=='ANNULE' and 'SCHEDULE_CHANGED' in (x['last_error'] or '') for x in reminders(e,sid))
