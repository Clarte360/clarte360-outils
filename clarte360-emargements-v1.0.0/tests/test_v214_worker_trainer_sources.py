from datetime import datetime
from pathlib import Path
from db import make_engine, init_db, one
from services import (create_action, add_participant, add_slot, ensure_tokens_and_events,
                      email_event_due_utc, add_trainer, create_trainer_invitation,
                      trainer_by_invite, accept_trainer_invitation, verify_trainer_login,
                      assign_trainer, trainer_actions)
import source_store


def eng(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'v214.db')); init_db(e); return e


def action(e,no='V214'):
    return create_action(e,{'action_no':no,'title':'Test nuit','subtitle':None,'nature':'Formation','mode':'INDIVIDUEL','client_name':None,'client_type':'Particulier','group_code':None,'planned_hours':1,'expected_participants':1,'admin_email':'a@b.fr','trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'},'test')


def test_overnight_email_deadlines_cross_midnight(tmp_path):
    e=eng(tmp_path); aid=action(e)
    pid,_=add_participant(e,aid,{'individual_action_no':'V214','last_name':'NUIT','birth_name':None,'first_name':'Test','birth_date':None,'email':'test@example.org','employee_id':None,'company_name':None,'phone':None},'test')
    sid=add_slot(e,aid,'2026-09-03','23:25','00:25','test',-60,20,120,1440)
    sl=one(e,'SELECT * FROM slots WHERE id=:s',{'s':sid})
    assert email_event_due_utc(sl,'INITIAL','Europe/Paris').isoformat()=='2026-09-03T21:25:00+00:00'
    assert email_event_due_utc(sl,'RELANCE_1','Europe/Paris').isoformat()=='2026-09-03T22:45:00+00:00'
    assert email_event_due_utc(sl,'RELANCE_2','Europe/Paris').isoformat()=='2026-09-04T00:25:00+00:00'
    ensure_tokens_and_events(e,aid,'https://example.org','Europe/Paris')
    rows={x['event_type']:x['due_at'] for x in __import__('db').q(e,'SELECT event_type,due_at FROM email_events WHERE slot_id=:s',{'s':sid})}
    assert rows['INITIAL']=='2026-09-03T21:25:00+00:00'
    assert rows['RELANCE_1']=='2026-09-03T22:45:00+00:00'
    assert rows['RELANCE_2']=='2026-09-04T00:25:00+00:00'


def test_trainer_invitation_and_portal_actions(tmp_path):
    e=eng(tmp_path); aid=action(e,'TR-V214')
    tid=add_trainer(e,'Formateur Test','formateur@example.org','0600000000','admin')
    token=create_trainer_invitation(e,tid,'admin')
    assert token and trainer_by_invite(e,token)['id']==tid
    ok,msg=accept_trainer_invitation(e,token,'MotDePasseTresFort2026!')
    assert ok, msg
    tr=verify_trainer_login(e,'formateur@example.org','MotDePasseTresFort2026!')
    assert tr and tr['id']==tid
    assign_trainer(e,aid,tid,'admin')
    acts=trainer_actions(e,tid)
    assert [a['action_no'] for a in acts]==['TR-V214']


def test_import_source_snapshot_is_persistent(tmp_path, monkeypatch):
    store=tmp_path/'sources'; monkeypatch.setattr(source_store,'STORE_DIR',store); monkeypatch.setattr(source_store,'META_PATH',store/'sources.json')
    info=source_store.save_uploaded_source('CLARTE360','base.xlsm',b'abc123')
    data,read_info=source_store.read_snapshot('CLARTE360')
    assert data==b'abc123'
    assert Path(info['snapshot_path']).exists()
    assert read_info['original_name']=='base.xlsm'

def test_worker_guard_repairs_stale_overnight_due_without_early_send(tmp_path, monkeypatch):
    import worker
    from db import execute, q
    e=eng(tmp_path); aid=action(e,'WG-V214')
    pid,_=add_participant(e,aid,{'individual_action_no':'WG','last_name':'NUIT','birth_name':None,'first_name':'Worker','birth_date':None,'email':'worker@example.org','employee_id':None,'company_name':None,'phone':None},'test')
    sid=add_slot(e,aid,'2099-09-03','23:25','00:25','test',-60,20,120,1440)
    execute(e,"UPDATE actions SET status='ACTIVE' WHERE id=:a",{'a':aid})
    ensure_tokens_and_events(e,aid,'https://example.org','Europe/Paris')
    execute(e,"UPDATE email_events SET due_at='2000-01-01T00:00:00+00:00' WHERE slot_id=:s",{'s':sid})
    dburl='sqlite:///'+str(tmp_path/'v214.db')
    monkeypatch.setattr(worker,'load_cfg',lambda:{'database':{'url':dburl},'app':{'base_url':'https://example.org'},'email':{'enabled':True,'smtp_server':'x','smtp_port':587,'smtp_user':'u','smtp_password':'p','from_email':'f@example.org'}})
    sent=[]; monkeypatch.setattr(worker,'send_mail',lambda *a,**k: sent.append(a))
    worker.run_once()
    assert sent==[]
    rows=q(e,'SELECT event_type,due_at,status FROM email_events WHERE slot_id=:s ORDER BY event_type',{'s':sid})
    assert all(r['status']=='PENDING' for r in rows)
    assert all(r['due_at'].startswith('2099-09-') for r in rows)
