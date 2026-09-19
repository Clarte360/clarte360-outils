from db import make_engine, init_db, one, q
from services import upsert_pip_public_crm_contact, register_pip_public_callback

def eng(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'c.db')); init_db(e); return e

def test_callback_creates_activity_queue_and_updates_contact(tmp_path):
    e=eng(tmp_path)
    c=upsert_pip_public_crm_contact(e,'Ada','Lovelace','ADA@EXAMPLE.COM',phone='0600000000',job_title='Ingénieure',company='Analytical')
    old=c['updated_at']
    r=register_pip_public_callback(e,'evt-cb-1','ada@example.com',requested_at='2026-09-18T19:30:00+00:00')
    assert r['created'] is True
    ev=one(e,"SELECT * FROM crm_events WHERE contact_id=:c AND event_type='CALLBACK_REQUESTED'",{'c':c['id']})
    assert 'Demande à être recontacté(e)' in ev['details_json'] and 'PIP-RIASEC PUBLIC' in ev['details_json']
    n=one(e,'SELECT * FROM crm_callback_notifications WHERE external_event_id=:x',{'x':'evt-cb-1'})
    assert n['status']=='A_ENVOYER' and n['contact_id']==c['id']
    assert one(e,'SELECT updated_at FROM crm_contacts WHERE id=:i',{'i':c['id']})['updated_at'] >= old

def test_callback_replay_is_idempotent(tmp_path):
    e=eng(tmp_path); c=upsert_pip_public_crm_contact(e,'Ada','Lovelace','ada@example.com')
    assert register_pip_public_callback(e,'evt-same','ada@example.com')['created'] is True
    assert register_pip_public_callback(e,'evt-same','ada@example.com')['created'] is False
    assert len(q(e,"SELECT * FROM crm_events WHERE contact_id=:c AND event_type='CALLBACK_REQUESTED'",{'c':c['id']}))==1
    assert len(q(e,'SELECT * FROM crm_callback_notifications WHERE external_event_id=:e',{'e':'evt-same'}))==1

def test_callback_requires_existing_crm_contact(tmp_path):
    e=eng(tmp_path)
    try: register_pip_public_callback(e,'evt-x','nobody@example.com')
    except ValueError as ex: assert 'introuvable' in str(ex)
    else: assert False

def test_callback_worker_email_contains_only_commercial_fields(tmp_path, monkeypatch):
    import worker
    e=eng(tmp_path)
    upsert_pip_public_crm_contact(e,'Ada','Lovelace','ada@example.com',phone='0600000000',job_title='Ingénieure',company='Analytical')
    register_pip_public_callback(e,'evt-mail','ada@example.com',requested_at='2026-09-18T19:30:00+00:00')
    sent=[]
    monkeypatch.setattr(worker,'send_mail',lambda cfg,to,subject,body,attachments=None: sent.append((to,subject,body)))
    assert worker._run_crm_callback_notifications(e,{'from_email':'fallback@clarte360.com'},{'pip_public':{'callback_email':'interne@clarte360.com'}})==1
    assert sent and sent[0][0]=='interne@clarte360.com'
    body=sent[0][2]
    for expected in ('Ada','Lovelace','ada@example.com','0600000000','Ingénieure','Analytical','Demande à être recontacté(e)'):
        assert expected in body
    for forbidden in ('Holland','RIASEC score','pip_answers','onet_answers','study_id','pseudonym'):
        assert forbidden not in body
    assert one(e,'SELECT status FROM crm_callback_notifications WHERE external_event_id=:e',{'e':'evt-mail'})['status']=='ENVOYE'
