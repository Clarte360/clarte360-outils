from datetime import datetime, timezone, timedelta
from db import make_engine, init_db, one, q, execute
from services import *


def setup(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'i5.db'));init_db(e);oid=ensure_default_organization(e)
    aid=create_action(e,{'action_no':'I5-001','title':'I5','subtitle':None,'nature':'FORMATION','mode':'INTRA','client_name':'Client','client_type':None,'group_code':None,'planned_hours':1,'expected_participants':1,'admin_email':'a@b.fr','trainer_name':'T','trainer_email':'t@b.fr','location':'Paris','notes':None,'source':'TEST'},'admin')
    execute(e,"UPDATE actions SET status='ACTIVE',organization_id=:o,start_date='2026-09-01',end_date='2026-09-01',use_quality_hot=1,use_quality_cold=1 WHERE id=:a",{'o':oid,'a':aid})
    pid=add_participant(e,aid,{'individual_action_no':'I5-001','last_name':'DUPONT','birth_name':None,'first_name':'Jean','birth_date':'1990-01-01','email':'j@x.fr','employee_id':None,'company_name':None,'phone':None},'admin')[0]
    sid=add_slot(e,aid,'2026-09-01','09:00','10:00','admin')
    return e,aid,pid,sid


def test_quality_only_one_automatic_event(tmp_path):
    e,a,p,s=setup(tmp_path);seed_standard_questionnaires(e,get_organization(e)['id']);prepare_quality_campaigns(e,a,'https://x','admin')
    events=q(e,'SELECT event_type,status FROM quality_email_events ORDER BY id')
    assert events and {x['event_type'] for x in events}=={'INITIAL'}


def test_manual_quality_reminder_reuses_campaign_and_token(tmp_path):
    e,a,p,s=setup(tmp_path);seed_standard_questionnaires(e,get_organization(e)['id']);prepare_quality_campaigns(e,a,'https://x','admin')
    camp=one(e,"SELECT * FROM quality_campaigns WHERE action_id=:a AND campaign_kind='HOT'",{'a':a});token=camp['token']
    execute(e,"UPDATE quality_email_events SET status='SENT' WHERE campaign_id=:c AND event_type='INITIAL'",{'c':camp['id']});execute(e,"UPDATE quality_campaigns SET status='SENT' WHERE id=:c",{'c':camp['id']})
    et=queue_quality_manual_reminder(e,camp['id'],'admin')
    camp2=one(e,'SELECT * FROM quality_campaigns WHERE id=:c',{'c':camp['id']})
    assert et=='MANUAL_1' and camp2['token']==token and camp2['manual_reminder_count']==1
    assert one(e,"SELECT COUNT(*) n FROM quality_campaigns WHERE action_id=:a AND campaign_kind='HOT'",{'a':a})['n']==1
    assert one(e,"SELECT COUNT(*) n FROM quality_email_events WHERE campaign_id=:c AND event_type='MANUAL_1'",{'c':camp['id']})['n']==1


def test_legacy_quality_reminders_are_neutralized(tmp_path):
    e,a,p,s=setup(tmp_path);seed_standard_questionnaires(e,get_organization(e)['id']);prepare_quality_campaigns(e,a,'https://x','admin')
    camp=one(e,"SELECT * FROM quality_campaigns WHERE action_id=:a AND campaign_kind='HOT'",{'a':a})
    execute(e,"INSERT INTO quality_email_events(campaign_id,event_type,due_at,status,created_at) VALUES(:c,'REMINDER_1',:n,'PENDING',:n)",{'c':camp['id'],'n':utcnow_iso()})
    reschedule_pending_quality_campaigns(e,a,'admin')
    row=one(e,"SELECT * FROM quality_email_events WHERE campaign_id=:c AND event_type='REMINDER_1'",{'c':camp['id']})
    assert row['status']=='SKIPPED'


def test_quality_stats_use_business_labels(tmp_path):
    e,a,p,s=setup(tmp_path);seed_standard_questionnaires(e,get_organization(e)['id']);prepare_quality_campaigns(e,a,'https://x','admin')
    camp=one(e,"SELECT * FROM quality_campaigns WHERE action_id=:a AND campaign_kind='HOT'",{'a':a}); qu=quality_questions(e,camp['id'])[0]
    save_quality_response(e,camp['id'],qu['id'],4,'beneficiary')
    stats=quality_question_stats(e)
    assert stats[0]['Rubrique']!='R01' and stats[0]['Question']==qu['question_text'] and stats[0]['Moyenne']==4.0
    summary=quality_management_summary(e)
    assert summary['rubric_averages']


def test_attendance_regularization_lists_only_finished_unresolved(tmp_path):
    e,a,p,s=setup(tmp_path)
    rows=attendance_regularization_items(e,action_id=a)
    assert any(x['participant_id']==p and x['slot_id']==s for x in rows)
    set_attendance_status(e,p,s,'ABSENT','test','admin')
    assert not attendance_regularization_items(e,action_id=a)

def test_trainer_feedback_created_for_all_action_trainers(tmp_path):
    e,a,p,s=setup(tmp_path);execute(e,"UPDATE actions SET use_trainer_feedback=1 WHERE id=:a",{'a':a})
    t1=add_trainer(e,'Formateur Un','u@x.fr','','admin');t2=add_trainer(e,'Formateur Deux','d@x.fr','','admin')
    assign_action_trainer(e,a,t1,'admin','REFERENT',True);assign_action_trainer(e,a,t2,'admin','INTERVENANT',False)
    seed_standard_questionnaires(e,get_organization(e)['id']);prepare_quality_campaigns(e,a,'https://x','admin')
    rows=q(e,"SELECT trainer_id FROM quality_campaigns WHERE action_id=:a AND campaign_kind='TRAINER'",{'a':a})
    assert {x['trainer_id'] for x in rows}=={t1,t2}
