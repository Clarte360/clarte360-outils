from db import make_engine,init_db,execute,one,utcnow_iso
from services import (create_professional_intervenant,create_professional_candidate,list_services,
 set_human_service_qualification,set_action_service_requirement,get_action_service_requirement,
 action_professional_eligibility,action_intervenant_candidates,assign_action_professional,assign_slot_professional)

def eng(tmp_path):
 e=make_engine('sqlite:///'+str(tmp_path/'j11.db'));init_db(e);return e

def action(e):
 n=utcnow_iso();return execute(e,"INSERT INTO actions(action_no,title,nature,mode,status,created_at,updated_at) VALUES('A-J11','Action J11','FORMATION','PRESENTIEL','BROUILLON',:n,:n)",{'n':n})

def test_action_requirement_uses_real_clarte360_service(tmp_path):
 e=eng(tmp_path);a=action(e);s=list_services(e,True)[0]
 ok,msg=set_action_service_requirement(e,a,s['id'],'admin',3,True)
 r=get_action_service_requirement(e,a)
 assert ok and not msg and r['service_id']==s['id'] and r['minimum_human_level']==3 and r['require_required_complete']==1

def test_human_qualification_controls_operational_eligibility(tmp_path):
 e=eng(tmp_path);a=action(e);s=list_services(e,True)[0];p=create_professional_intervenant(e,'Alice J11',actor='admin')
 set_action_service_requirement(e,a,s['id'],'admin',3,False)
 assert action_professional_eligibility(e,a,p)['status']=='NON_QUALIFIE'
 set_human_service_qualification(e,p,s['id'],3,'admin','Validé',True)
 x=action_professional_eligibility(e,a,p);assert x['eligible'] and x['status']=='QUALIFIE' and x['human_value']==3

def test_candidate_never_becomes_assignable(tmp_path):
 e=eng(tmp_path);a=action(e);p=create_professional_candidate(e,'Candidate J11',actor='admin')
 x=action_professional_eligibility(e,a,p)
 assert not x['eligible'] and x['status']=='INELIGIBLE'
 assert all(r['professional_person_id']!=p for r in action_intervenant_candidates(e,a,True))

def test_assignment_uses_stable_professional_person_and_legacy_trainer_bridge(tmp_path):
 e=eng(tmp_path);a=action(e);s=list_services(e,True)[0];p=create_professional_intervenant(e,'Bob J11',actor='admin')
 set_action_service_requirement(e,a,s['id'],'admin',3,False);set_human_service_qualification(e,p,s['id'],4,'admin','Expert',True)
 ok,msg=assign_action_professional(e,a,p,'admin',is_referent=True)
 tr=one(e,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':p})
 at=one(e,'SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t',{'a':a,'t':tr['trainer_id']})
 assert ok and not msg and at and at['active']==1

def test_exception_requires_reason_and_is_audited_for_slot(tmp_path):
 e=eng(tmp_path);a=action(e);s=list_services(e,True)[0];p=create_professional_intervenant(e,'Cara J11',actor='admin')
 set_action_service_requirement(e,a,s['id'],'admin',4,False);set_human_service_qualification(e,p,s['id'],2,'admin','Partiel',True)
 n=utcnow_iso();sl=execute(e,"INSERT INTO slots(action_id,slot_date,start_time,end_time,created_at,updated_at) VALUES(:a,'2026-09-21','09:00','12:00',:n,:n)",{'a':a,'n':n})
 ok,msg=assign_slot_professional(e,sl,p,'admin',allow_exception=True)
 assert not ok and 'justification' in msg.lower()
 ok,msg=assign_slot_professional(e,sl,p,'admin',reason='Continuité pédagogique validée par admin',allow_exception=True)
 assert ok
 ev=one(e,"SELECT * FROM audit_log WHERE action_id=:a AND event_type='SLOT_PROFESSIONAL_QUALIFICATION_OVERRIDE'",{'a':a})
 assert ev is not None
