from datetime import datetime, timezone
from db import make_engine,init_db,one,q,execute,utcnow_iso
from services import (
    ensure_default_organization,get_organization,create_action,add_participant,set_action_modules,
    seed_standard_questionnaires,get_standard_template,prepare_quality_campaigns,
    quality_questions,complete_quality_campaign,list_quality_issues,quality_token_url,
    purge_participant,purge_action,normalize_action_status,close_action
)


def eng():
    e=make_engine('sqlite:///:memory:');init_db(e);ensure_default_organization(e);return e

def action(e,pt='FORMATION',hot=True,cold=True):
    oid=get_organization(e)['id']
    aid=create_action(e,dict(action_no='A1',title='Test qualité',subtitle=None,nature='Formation',mode='INDIVIDUEL',client_name=None,client_type='Particulier',group_code=None,planned_hours=1,expected_participants=1,admin_email='a@x.fr',trainer_name=None,trainer_email=None,location=None,notes=None,source='TEST'),'test')
    execute(e,'UPDATE actions SET start_date=:s,end_date=:d WHERE id=:a',{'s':'2026-01-01','d':'2026-01-10','a':aid})
    set_action_modules(e,aid,pt,False,hot,cold,False,oid,None,'test')
    return aid

def test_standard_catalog_seeded_and_codes_stable():
    e=eng();oid=get_organization(e)['id'];n=seed_standard_questionnaires(e,oid,'test')
    assert n==13
    assert seed_standard_questionnaires(e,oid,'test')==0
    tpl=get_standard_template(e,oid,'FORMATION','HOT')
    assert tpl and tpl['version']=='2.0'
    codes=[x['question_code'] for x in q(e,'SELECT * FROM questionnaire_questions WHERE template_id=:t ORDER BY position',{'t':tpl['id']})]
    assert 'F-CH-R01-01' in codes and 'F-CH-R11-01' in codes

def test_prepare_hot_and_cold_campaigns_without_attendance():
    e=eng();oid=get_organization(e)['id'];seed_standard_questionnaires(e,oid)
    aid=action(e);pid,_=add_participant(e,aid,dict(individual_action_no='A1',last_name='DUPONT',birth_name=None,first_name='Jean',birth_date=None,email='j@x.fr',employee_id=None,company_name=None,phone=None),'test')
    made=prepare_quality_campaigns(e,aid,'https://example.test','test')
    assert len(made)==2
    camps=q(e,'SELECT * FROM quality_campaigns WHERE action_id=:a ORDER BY campaign_kind',{'a':aid})
    assert {x['campaign_kind'] for x in camps}=={'HOT','COLD'}
    assert all(quality_token_url(x['token'],'https://example.test').startswith('https://example.test?quality_token=') for x in camps)
    assert one(e,'SELECT COUNT(*) n FROM quality_email_events')['n']==6

def test_bilan_cold_due_is_about_six_months():
    e=eng();oid=get_organization(e)['id'];seed_standard_questionnaires(e,oid)
    aid=action(e,'BILAN_COMPETENCES',False,True);add_participant(e,aid,dict(individual_action_no='A1',last_name='D',birth_name=None,first_name='J',birth_date=None,email='j@x.fr',employee_id=None,company_name=None,phone=None),'test')
    prepare_quality_campaigns(e,aid,'https://example.test')
    c=one(e,'SELECT * FROM quality_campaigns WHERE action_id=:a',{'a':aid});d=datetime.fromisoformat(c['due_at'])
    assert d.date().isoformat()=='2026-07-10'

def test_complete_campaign_snapshots_answers_and_stops_reminders():
    e=eng();oid=get_organization(e)['id'];seed_standard_questionnaires(e,oid)
    aid=action(e,'FORMATION',True,False);add_participant(e,aid,dict(individual_action_no='A1',last_name='D',birth_name=None,first_name='J',birth_date=None,email='j@x.fr',employee_id=None,company_name=None,phone=None),'test')
    prepare_quality_campaigns(e,aid,'https://example.test');c=one(e,'SELECT * FROM quality_campaigns WHERE action_id=:a',{'a':aid});qs=quality_questions(e,c['id'])
    answers={x['id']:(5 if x['response_type']=='SCALE_1_5' else (9 if x['response_type']=='NPS_0_10' else ('Non' if x['response_type']=='CHOICE_SINGLE' else 'Très bien'))) for x in qs}
    complete_quality_campaign(e,c['id'],answers,'beneficiary')
    assert one(e,'SELECT status FROM quality_campaigns WHERE id=:i',{'i':c['id']})['status']=='COMPLETED'
    r=one(e,'SELECT * FROM quality_responses WHERE campaign_id=:c LIMIT 1',{'c':c['id']})
    assert r['question_text_snapshot'] and r['rubric_code'].startswith('R')
    assert one(e,"SELECT COUNT(*) n FROM quality_email_events WHERE campaign_id=:c AND status='PENDING'",{'c':c['id']})['n']==0

def test_quality_difficulty_creates_issue():
    e=eng();oid=get_organization(e)['id'];seed_standard_questionnaires(e,oid)
    aid=action(e,'FORMATION',True,False);add_participant(e,aid,dict(individual_action_no='A1',last_name='D',birth_name=None,first_name='J',birth_date=None,email='j@x.fr',employee_id=None,company_name=None,phone=None),'test')
    prepare_quality_campaigns(e,aid,'https://example.test');c=one(e,'SELECT * FROM quality_campaigns WHERE action_id=:a',{'a':aid});qs=quality_questions(e,c['id']);answers={}
    for x in qs:
        if x['response_type']=='SCALE_1_5': answers[x['id']]=5
        elif x['response_type']=='NPS_0_10': answers[x['id']]=8
        elif x['rubric_code']=='R12': answers[x['id']]='Oui - réclamation'
        else: answers[x['id']]='RAS'
    complete_quality_campaign(e,c['id'],answers)
    issues=list_quality_issues(e,aid)
    assert len(issues)==1 and issues[0]['issue_type']=='RECLAMATION'

def test_participant_purge_removes_quality_issue_and_campaign():
    e=eng();oid=get_organization(e)['id'];seed_standard_questionnaires(e,oid)
    aid=action(e,'FORMATION',True,False);pid,_=add_participant(e,aid,dict(individual_action_no='A1',last_name='D',birth_name=None,first_name='J',birth_date=None,email='j@x.fr',employee_id=None,company_name=None,phone=None),'test')
    prepare_quality_campaigns(e,aid,'https://example.test');c=one(e,'SELECT id FROM quality_campaigns WHERE participant_id=:p',{'p':pid})
    execute(e,"INSERT INTO quality_issues(action_id,campaign_id,issue_type,title,status,created_at) VALUES(:a,:c,'DIFFICULTE_ALEA','x','OUVERTE',:n)",{'a':aid,'c':c['id'],'n':utcnow_iso()})
    purge_participant(e,pid,'admin')
    assert one(e,'SELECT id FROM quality_campaigns WHERE participant_id=:p',{'p':pid}) is None
    assert one(e,'SELECT id FROM quality_issues WHERE campaign_id=:c',{'c':c['id']}) is None

def test_action_purge_removes_quality_children():
    e=eng();oid=get_organization(e)['id'];seed_standard_questionnaires(e,oid)
    aid=action(e,'FORMATION',True,False);add_participant(e,aid,dict(individual_action_no='A1',last_name='D',birth_name=None,first_name='J',birth_date=None,email='j@x.fr',employee_id=None,company_name=None,phone=None),'test')
    prepare_quality_campaigns(e,aid,'https://example.test');c=one(e,'SELECT id FROM quality_campaigns WHERE action_id=:a',{'a':aid})
    iid=execute(e,"INSERT INTO quality_issues(action_id,campaign_id,issue_type,title,status,created_at) VALUES(:a,:c,'DIFFICULTE_ALEA','x','OUVERTE',:n)",{'a':aid,'c':c['id'],'n':utcnow_iso()})
    execute(e,"INSERT INTO improvement_actions(issue_id,action_id,title,status,created_at) VALUES(:i,:a,'améliorer','A_FAIRE',:n)",{'i':iid,'a':aid,'n':utcnow_iso()})
    purge_action(e,aid,'admin')
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':aid}) is None
    assert one(e,'SELECT id FROM quality_issues WHERE action_id=:a',{'a':aid}) is None
    assert one(e,'SELECT id FROM improvement_actions WHERE action_id=:a',{'a':aid}) is None
