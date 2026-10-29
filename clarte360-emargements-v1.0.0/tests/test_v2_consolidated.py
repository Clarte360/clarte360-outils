from pathlib import Path
import tempfile
from db import make_engine,init_db,one,execute,utcnow_iso
from services import (
    ensure_default_organization,upsert_organization,add_agency,list_agencies,
    create_action,safe_set_action_modules,archive_action,unarchive_action,
    search_actions,migrate_legacy_action_statuses,create_questionnaire_template,
    create_quality_campaign,normalize_action_status
)
from worker import _claim_event,_quarantine_stale_sending


def eng():
    td=tempfile.TemporaryDirectory(); e=make_engine('sqlite:///'+str(Path(td.name)/'t.db')); init_db(e); e._td=td; return e

def action(e,no='A1'):
    return create_action(e,{'action_no':no,'title':'Test','subtitle':None,'nature':'Formation','mode':'INTER','client_name':'Client ABC','client_type':'Professionnel','group_code':None,'planned_hours':7,'expected_participants':2,'admin_email':'a@x.fr','trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'},'test')

def test_organization_agency_and_action_modules():
    e=eng(); oid=ensure_default_organization(e)
    upsert_organization(e,oid,{'name':'OF Démo','legal_name':'OF Démo SAS','timezone':'Europe/Paris','privacy_notice':'Notice','retention_months':60},'test')
    gid=add_agency(e,oid,{'name':'Agence Nord','city':'Lille'},'test')
    assert list_agencies(e,oid)[0]['name']=='Agence Nord'
    aid=action(e); safe_set_action_modules(e,aid,'COACHING',False,True,True,True,oid,gid,'test')
    a=one(e,'SELECT * FROM actions WHERE id=:a',{'a':aid})
    assert (a['prestation_type'],a['use_attendance'],a['agency_id'])==('COACHING',0,gid)

def test_modules_locked_after_sent_quality_campaign():
    e=eng(); oid=ensure_default_organization(e); aid=action(e)
    tid=create_questionnaire_template(e,oid,'HOT','1','FORMATION','HOT','Test',[{'question_code':'Q1','rubric_code':'R01','response_type':'TEXT','question_text':'Avis ?'}])
    cid,_=create_quality_campaign(e,aid,tid,'HOT',utcnow_iso(),actor='test')
    execute(e,"UPDATE quality_campaigns SET status='SENT' WHERE id=:i",{'i':cid})
    try:
        safe_set_action_modules(e,aid,'FORMATION',True,True,False,False,oid,None,'test')
        assert False,'expected lock'
    except ValueError:
        pass

def test_archive_unarchive_and_search_participant_client():
    e=eng(); aid=action(e,'A-SEARCH')
    execute(e,"INSERT INTO participants(action_id,last_name,first_name,email,created_at) VALUES(:a,'DUPONT','Alice','alice@example.fr',:c)",{'a':aid,'c':utcnow_iso()})
    assert search_actions(e,'dupont')[0]['id']==aid
    assert archive_action(e,aid,'test')[0]
    assert normalize_action_status(one(e,'SELECT status FROM actions WHERE id=:a',{'a':aid})['status'])=='ARCHIVEE'
    assert search_actions(e,'A-SEARCH',include_archived=False)==[]
    assert unarchive_action(e,aid,'test')[0]
    assert one(e,'SELECT status FROM actions WHERE id=:a',{'a':aid})['status']=='CLOTUREE'

def test_legacy_status_normalization():
    e=eng(); aid=action(e); execute(e,"UPDATE actions SET status='TERMINEE' WHERE id=:a",{'a':aid})
    assert migrate_legacy_action_statuses(e)==1
    assert one(e,'SELECT status FROM actions WHERE id=:a',{'a':aid})['status']=='CLOTUREE'

def test_worker_atomic_claim_prevents_second_claim():
    e=eng(); aid=action(e); execute(e,"INSERT INTO participants(action_id,last_name,first_name,email,created_at) VALUES(:a,'D','A','a@b.fr',:c)",{'a':aid,'c':utcnow_iso()}); pid=one(e,'SELECT id FROM participants')['id']
    execute(e,"INSERT INTO slots(action_id,slot_date,start_time,end_time,public_token,created_at,updated_at) VALUES(:a,'2026-09-03','09:00','10:00','x',:c,:c)",{'a':aid,'c':utcnow_iso()}); sid=one(e,'SELECT id FROM slots')['id']
    eid=execute(e,"INSERT INTO email_events(participant_id,slot_id,event_type,due_at) VALUES(:p,:s,'INITIAL',:d)",{'p':pid,'s':sid,'d':utcnow_iso()})
    assert _claim_event(e,eid)
    assert _claim_event(e,eid) is None

def test_stale_sending_is_quarantined_not_requeued():
    e=eng(); aid=action(e); execute(e,"INSERT INTO participants(action_id,last_name,first_name,email,created_at) VALUES(:a,'D','A','a@b.fr',:c)",{'a':aid,'c':utcnow_iso()}); pid=one(e,'SELECT id FROM participants')['id']
    execute(e,"INSERT INTO slots(action_id,slot_date,start_time,end_time,public_token,created_at,updated_at) VALUES(:a,'2026-09-03','09:00','10:00','x',:c,:c)",{'a':aid,'c':utcnow_iso()}); sid=one(e,'SELECT id FROM slots')['id']
    eid=execute(e,"INSERT INTO email_events(participant_id,slot_id,event_type,due_at,status,claimed_at) VALUES(:p,:s,'INITIAL',:d,'SENDING','2000-01-01T00:00:00+00:00')",{'p':pid,'s':sid,'d':utcnow_iso()})
    assert _quarantine_stale_sending(e)==1
    assert one(e,'SELECT status FROM email_events WHERE id=:i',{'i':eid})['status']=='UNKNOWN_DELIVERY'
