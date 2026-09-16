from datetime import datetime
from zoneinfo import ZoneInfo
from db import make_engine, init_db, execute, one, q, utcnow_iso
from services import (
    create_action, add_participant, add_slot, add_trainer, assign_trainer,
    set_attendance_status, countersign_slot, create_beneficiary_report,
    ensure_default_organization, quality_source_counts, quality_plan_counts,
    create_quality_event, add_quality_event_action,
)
import worker


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); ensure_default_organization(e); return e


def action(e,no='J2C-001'):
    return create_action(e,dict(action_no=no,title='Session Teams',subtitle=None,nature='FORMATION',mode='DISTANCIEL',client_name='Client',client_type='Entreprise',group_code=None,planned_hours=1,expected_participants=1,admin_email='admin@example.org',trainer_name=None,trainer_email=None,location='Teams',notes=None,source='TEST'),'test')


def test_worker_handles_teams_h2_and_h15(monkeypatch):
    e=eng(); aid=action(e)
    tid=add_trainer(e,'Dominique BRIET','dbriet@clarte360.com','','test'); assign_trainer(e,aid,tid,'test')
    pid,_=add_participant(e,aid,{'last_name':'PAQUETTE','first_name':'Quentin','birth_date':'1990-01-01','email':'q@example.org'},'test')
    sid=add_slot(e,aid,'2026-09-16','18:00','19:00','test')
    due='2020-01-01T00:00:00+00:00'
    for typ,participant,trainer,email in [
        ('TEAMS_REMINDER_H2',pid,None,'q@example.org'),
        ('TEAMS_REMINDER_H15',None,tid,'dbriet@clarte360.com')]:
        execute(e,"""INSERT INTO communication_events(action_id,participant_id,trainer_id,slot_id,communication_type,recipient_email,trigger_mode,status,due_at,attempts,created_at,updated_at)
          VALUES(:a,:p,:t,:s,:ct,:em,'AUTO','A_ENVOYER',:d,0,:n,:n)""",{'a':aid,'p':participant,'t':trainer,'s':sid,'ct':typ,'em':email,'d':due,'n':utcnow_iso()})
    sent=[]
    monkeypatch.setattr(worker,'send_mail',lambda cfg,to,subject,body: sent.append((to,subject,body)))
    monkeypatch.setattr(worker,'organization_runtime_config',lambda eng,aid:{'organization':{'name':'Clarté360'}})
    assert worker._run_communication_events(e,{},'https://emargements.clarte360.com')==2
    assert len(sent)==2
    all_body=' '.join(x[2] for x in sent)
    assert "N° d’action : J2C-001" in all_body
    assert 'onglet <strong>Teams</strong>' in all_body
    assert 'trainer_portal=1' in all_body and 'beneficiary_portal=1' in all_body
    assert all(r['status']=='ENVOYE' for r in q(e,"SELECT status FROM communication_events"))


def test_assigned_trainer_can_use_name_certification_without_canvas():
    e=eng(); aid=action(e,'J2C-CS')
    tid=add_trainer(e,'Dominique BRIET','dbriet@clarte360.com','','test'); assign_trainer(e,aid,tid,'test')
    pid,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'a@example.org'},'test')
    sid=add_slot(e,aid,'2026-09-16','18:00','19:00','test')
    set_attendance_status(e,pid,sid,'ABSENT','test','test')
    now=datetime(2026,9,16,19,5,tzinfo=ZoneInfo('Europe/Paris'))
    ok,msg=countersign_slot(e,sid,'Dominique BRIET','dbriet@clarte360.com','trainer:1','Je certifie',trainer_id=tid,signature_bytes=None,now=now)
    assert ok,msg
    row=one(e,'SELECT method,signature_sha256 FROM trainer_countersignatures_v3 WHERE slot_id=:s AND trainer_id=:t',{'s':sid,'t':tid})
    assert row['method']=='NOM_PRENOM' and row['signature_sha256'] is None


def test_new_beneficiary_report_creates_j2_quality_event_and_legacy_trace():
    e=eng(); aid=action(e,'J2C-Q')
    bid=execute(e,"INSERT INTO beneficiaries(public_id,last_name,first_name,birth_date,current_email,created_at,updated_at) VALUES('B-J2C','DUPONT','Anne','1990-01-01','a@example.org',:n,:n)",{'n':utcnow_iso()})
    execute(e,"INSERT INTO participants(action_id,last_name,first_name,email,active,created_at,beneficiary_id) VALUES(:a,'DUPONT','Anne','a@example.org',1,:n,:b)",{'a':aid,'b':bid,'n':utcnow_iso()})
    rid=create_beneficiary_report(e,aid,bid,'Besoin de contact','Merci de me rappeler','Test',False)
    ev=one(e,"SELECT * FROM quality_events WHERE action_id=:a AND origin='SIGNALEMENT_BENEFICIAIRE'",{'a':aid})
    assert ev and ev['event_type']=='INFORMATION' and ev['subject']=='Merci de me rappeler'
    legacy=one(e,"SELECT * FROM quality_issues WHERE source_role='BENEFICIAIRE' AND source_ref=:r",{'r':str(rid)})
    assert legacy and legacy['status']=='MIGRE'
    counts=quality_source_counts(e,[aid]); assert counts['reports']==1


def test_quality_plan_counts_distinguish_in_progress_verify_closed_and_overdue():
    e=eng(); aid=action(e,'J2C-P')
    ev=create_quality_event(e,'QUESTIONNAIRES','DIFFICULTE','Point 2/5','',actor='admin',action_id=aid)
    a1=add_quality_event_action(e,ev,'Corriger Teams','admin',due_at='2020-01-01')
    a2=add_quality_event_action(e,ev,'Vérifier efficacité','admin')
    execute(e,"UPDATE quality_event_actions SET status='A_VERIFIER' WHERE id=:i",{'i':a2})
    a3=add_quality_event_action(e,ev,'Clôturée','admin')
    execute(e,"UPDATE quality_event_actions SET status='TERMINEE' WHERE id=:i",{'i':a3})
    c=quality_plan_counts(e,[aid])
    assert c=={'total':3,'in_progress':1,'to_verify':1,'closed':1,'overdue':1}
