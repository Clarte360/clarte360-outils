from datetime import datetime, timedelta, timezone
import pytest
from db import make_engine,init_db,one,q,execute,utcnow_iso
from services import *

def eng():
    e=make_engine('sqlite:///:memory:');init_db(e);ensure_default_organization(e);return e

def base_action(e):
    aid=create_action(e,dict(action_no='J2',title='J2 qualité',subtitle=None,nature='Formation',mode='INDIVIDUEL',client_name=None,client_type='Particulier',group_code=None,planned_hours=1,expected_participants=1,admin_email='a@x.fr',trainer_name=None,trainer_email=None,location=None,notes=None,source='TEST'),'test')
    execute(e,"UPDATE actions SET start_date='2026-01-01',end_date='2026-01-02' WHERE id=:a",{'a':aid})
    return aid

def campaign(e,due):
    aid=base_action(e); oid=get_organization(e)['id'];seed_standard_questionnaires(e,oid)
    pid,_=add_participant(e,aid,dict(individual_action_no='J2',last_name='D',birth_name=None,first_name='J',birth_date=None,email='j@x.fr',employee_id=None,company_name=None,phone=None),'test')
    tpl=get_standard_template(e,oid,'FORMATION','HOT')
    cid,_=create_quality_campaign(e,aid,tpl['id'],'HOT',due.isoformat(),participant_id=pid,actor='test')
    return aid,cid

def answers_for(e,cid,score=5):
    out={}
    for x in quality_questions(e,cid):
        out[x['id']]=score if x['response_type']=='SCALE_1_5' else (9 if x['response_type']=='NPS_0_10' else ('Non' if x['response_type']=='CHOICE_SINGLE' else 'RAS'))
    return out

def test_future_questionnaire_is_server_side_blocked():
    e=eng();aid,cid=campaign(e,datetime.now(timezone.utc)+timedelta(days=2));c=one(e,'SELECT * FROM quality_campaigns WHERE id=:i',{'i':cid})
    assert quality_campaign_availability(c)=='FUTURE'
    with pytest.raises(ValueError,match='disponible à partir'):
        complete_quality_campaign(e,cid,answers_for(e,cid),'beneficiary')
    assert one(e,'SELECT COUNT(*) n FROM quality_responses WHERE campaign_id=:c',{'c':cid})['n']==0

def test_due_questionnaire_opens_and_low_score_creates_review_point_not_complaint():
    e=eng();aid,cid=campaign(e,datetime.now(timezone.utc)-timedelta(minutes=1));complete_quality_campaign(e,cid,answers_for(e,cid,3),'beneficiary')
    pts=quality_review_points(e,aid,True);assert pts and all(p['score']<=3 for p in pts)
    assert not list_quality_events(e,aid)

def test_quality_event_full_lifecycle_and_capa():
    e=eng();aid=base_action(e);eid=create_quality_event(e,'CONFORMITE','NON_CONFORMITE','Écart test','Description','admin',action_id=aid,severity='MAJEURE')
    add_quality_event_action(e,eid,'Corriger','admin',owner_name='Dominique',due_at='2026-01-01T00:00:00+00:00')
    update_quality_event(e,eid,'admin',status='EN_TRAITEMENT',cause_analysis='Cause identifiée',effectiveness_criteria='Contrôle')
    update_quality_event(e,eid,'admin',status='A_VERIFIER',effectiveness_result='Conforme')
    update_quality_event(e,eid,'admin',status='CLOTURE',closure_comment='Efficacité vérifiée')
    ev=one(e,'SELECT * FROM quality_events WHERE id=:i',{'i':eid});assert ev['status']=='CLOTURE' and ev['closed_at']
    assert len(quality_event_actions(e,eid))==1

def test_dashboard_zero_response_is_none_not_zero_score():
    e=eng();aid,cid=campaign(e,datetime.now(timezone.utc)+timedelta(days=2));d=quality_dashboard_v31(e,action_id=aid)
    assert d['by_kind']['HOT']['score'] is None and d['by_kind']['HOT']['responses']==0

def test_email_history_exposes_manual_and_initial_events():
    e=eng();aid,cid=campaign(e,datetime.now(timezone.utc)-timedelta(minutes=1));schedule_quality_email_events(e,cid,utcnow_iso(),'HOT');queue_quality_manual_reminder(e,cid,'admin')
    hist=quality_campaign_email_history(e,cid);assert any(x['event_type']=='INITIAL' for x in hist) and any(x['event_type'].startswith('MANUAL_') for x in hist)
