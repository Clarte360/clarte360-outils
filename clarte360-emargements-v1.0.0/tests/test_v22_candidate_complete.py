from datetime import datetime, timezone, timedelta
from pathlib import Path

from db import make_engine, init_db, one, q, execute, utcnow_iso
from services import (
    ensure_default_organization, create_action, configure_final_transmission,
    queue_client_transmission, portal_retention_candidates,
    mark_portal_retention_warning, due_portal_purges,
)


def setup(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'candidate.db'));init_db(e);ensure_default_organization(e)
    aid=create_action(e,{
        'action_no':'CLA-CAND','title':'Candidate','subtitle':None,'nature':'FORMATION','mode':'INTRA',
        'client_name':'Client','client_type':None,'group_code':None,'planned_hours':1,'expected_participants':1,
        'admin_email':'admin@x.fr','trainer_name':'T','trainer_email':'t@x.fr','location':'Paris','notes':None,'source':'TEST'
    },'admin')
    return e,aid


def test_candidate_schema_client_transmission_and_portal_retention(tmp_path):
    e,a=setup(tmp_path)
    cols={r['name'] for r in q(e,'PRAGMA table_info(client_transmissions)')}
    assert {'campaign_id','claimed_at','claim_token','attempts'} <= cols
    pcols={r['name'] for r in q(e,'PRAGMA table_info(beneficiary_portal_accounts)')}
    assert {'portal_warning_sent_at','portal_purge_due_at'} <= pcols


def test_client_transmission_queue_is_idempotent(tmp_path):
    e,a=setup(tmp_path)
    first=queue_client_transmission(e,a,'FINAL','x.zip',['a@x.fr','a@x.fr'],'admin')
    second=queue_client_transmission(e,a,'FINAL','x.zip',['a@x.fr'],'admin')
    assert len(first)==1
    assert second==[]
    assert one(e,"SELECT COUNT(*) n FROM client_transmissions WHERE action_id=:a",{'a':a})['n']==1


def test_portal_retention_warning_then_due_purge(tmp_path):
    e,a=setup(tmp_path)
    old=(datetime.now(timezone.utc)-timedelta(days=400)).date().isoformat()
    execute(e,"UPDATE actions SET start_date=:d,end_date=:d WHERE id=:a",{'d':old,'a':a})
    bid=execute(e,"INSERT INTO beneficiaries(public_id,last_name,first_name,birth_date,current_email,active,created_at,updated_at) VALUES('BC','DURAND','Marie','1990-01-01','m@x.fr',1,:n,:n)",{'n':utcnow_iso()})
    execute(e,"INSERT INTO beneficiary_portal_accounts(beneficiary_id,email,active,created_at,updated_at) VALUES(:b,'m@x.fr',1,:n,:n)",{'b':bid,'n':utcnow_iso()})
    execute(e,"INSERT INTO participants(action_id,last_name,first_name,birth_date,email,beneficiary_id,pin_hash,created_at) VALUES(:a,'DURAND','Marie','1990-01-01','m@x.fr',:b,'x',:n)",{'a':a,'b':bid,'n':utcnow_iso()})
    candidates=portal_retention_candidates(e,12,30)
    assert [x['id'] for x in candidates]==[bid]
    mark_portal_retention_warning(e,bid,30,'test')
    row=one(e,'SELECT portal_warning_sent_at,portal_purge_due_at FROM beneficiary_portal_accounts WHERE beneficiary_id=:b',{'b':bid})
    assert row['portal_warning_sent_at'] and row['portal_purge_due_at']
    execute(e,"UPDATE beneficiary_portal_accounts SET portal_purge_due_at=:d WHERE beneficiary_id=:b",{'d':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),'b':bid})
    assert [x['id'] for x in due_portal_purges(e)]==[bid]


def test_final_transmission_configuration_does_not_send_when_disabled(tmp_path):
    e,a=setup(tmp_path)
    execute(e,"UPDATE actions SET client_quality_email='q@x.fr',client_training_email='f@x.fr' WHERE id=:a",{'a':a})
    configure_final_transmission(e,a,False,True,True,None,None,None,'admin')
    assert one(e,'SELECT transmit_final_bundle FROM actions WHERE id=:a',{'a':a})['transmit_final_bundle']==0

def test_new_action_prevents_portal_purge_even_after_warning(tmp_path):
    e,a=setup(tmp_path)
    old=(datetime.now(timezone.utc)-timedelta(days=400)).date().isoformat()
    execute(e,"UPDATE actions SET start_date=:d,end_date=:d WHERE id=:a",{'d':old,'a':a})
    bid=execute(e,"INSERT INTO beneficiaries(public_id,last_name,first_name,birth_date,current_email,active,created_at,updated_at) VALUES('BN','DUPONT','Luc','1990-01-01','l@x.fr',1,:n,:n)",{'n':utcnow_iso()})
    execute(e,"INSERT INTO beneficiary_portal_accounts(beneficiary_id,email,active,portal_warning_sent_at,portal_purge_due_at,created_at,updated_at) VALUES(:b,'l@x.fr',1,:n,:past,:n,:n)",{'b':bid,'n':utcnow_iso(),'past':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()})
    execute(e,"INSERT INTO participants(action_id,last_name,first_name,birth_date,email,beneficiary_id,pin_hash,created_at) VALUES(:a,'DUPONT','Luc','1990-01-01','l@x.fr',:b,'x',:n)",{'a':a,'b':bid,'n':utcnow_iso()})
    # A new/current action must cancel the purge condition without destroying history.
    a2=create_action(e,{'action_no':'CLA-NEW','title':'Nouvelle action','subtitle':None,'nature':'FORMATION','mode':'INTRA','client_name':'Client','client_type':None,'group_code':None,'planned_hours':1,'expected_participants':1,'admin_email':'admin@x.fr','trainer_name':'T','trainer_email':'t@x.fr','location':'Paris','notes':None,'source':'TEST'},'admin')
    today=datetime.now(timezone.utc).date().isoformat(); execute(e,"UPDATE actions SET start_date=:d,end_date=:d WHERE id=:a",{'d':today,'a':a2})
    execute(e,"INSERT INTO participants(action_id,last_name,first_name,birth_date,email,beneficiary_id,pin_hash,created_at) VALUES(:a,'DUPONT','Luc','1990-01-01','l@x.fr',:b,'x',:n)",{'a':a2,'b':bid,'n':utcnow_iso()})
    assert bid not in [x['id'] for x in due_portal_purges(e)]

def test_worker_sends_final_bundle_attachment(tmp_path, monkeypatch):
    e,a=setup(tmp_path)
    z=tmp_path/'261231 CLA-CAND DOCS STAGIAIRES.zip'; z.write_bytes(b'PK-test')
    execute(e,"UPDATE actions SET status='CLOTUREE',final_bundle_path=:p,final_bundle_generated_at=:n WHERE id=:a",{'p':str(z),'n':utcnow_iso(),'a':a})
    queue_client_transmission(e,a,'FINAL',z.name,['client@x.fr'],'admin')
    sent=[]
    import worker
    monkeypatch.setattr(worker,'send_mail',lambda cfg,to,subject,body,attachments=None: sent.append((to,subject,attachments)))
    n=worker._run_client_transmissions(e,{'enabled':True,'host':'smtp.test','from_email':'x@test'})
    assert n==1 and sent and sent[0][0]=='client@x.fr'
    assert sent[0][2][0]['filename']==z.name and sent[0][2][0]['data']==b'PK-test'
    assert one(e,"SELECT status FROM client_transmissions WHERE action_id=:a",{'a':a})['status']=='SENT'
