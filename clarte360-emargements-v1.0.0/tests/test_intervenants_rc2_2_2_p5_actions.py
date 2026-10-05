from db import make_engine,init_db,execute,utcnow_iso
from services import (create_professional_intervenant,list_services,set_action_service_requirement,
 set_human_service_qualification,action_professional_eligibility,assign_action_professional)

def _setup(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'p5.db')); init_db(e)
    svc=list_services(e,True)[0]
    p=create_professional_intervenant(e,'Test Retour Action',email='retour@example.test',collaboration_type='A_DEFINIR',actor='admin@test')
    n=utcnow_iso()
    aid=execute(e,"INSERT INTO actions(action_no,title,nature,mode,status,created_at,updated_at) VALUES('P5-001','Action P5','FORMATION','PRESENTIEL','BROUILLON',:n,:n)",{'n':n})
    set_action_service_requirement(e,aid,svc['id'],'admin@test',3,False)
    return e,aid,p,svc

def test_action_eligibility_recalculates_immediately_after_human_validation(tmp_path):
    e,aid,p,svc=_setup(tmp_path)
    before=action_professional_eligibility(e,aid,p)
    assert not before['eligible'] and before['status']=='NON_QUALIFIE'
    set_human_service_qualification(e,p,svc['id'],3,'admin@test','Validation P5',True)
    after=action_professional_eligibility(e,aid,p)
    assert after['eligible'] and after['status']=='QUALIFIE' and after['human_value']==3

def test_action_eligibility_still_blocks_insufficient_level(tmp_path):
    e,aid,p,svc=_setup(tmp_path)
    set_human_service_qualification(e,p,svc['id'],2,'admin@test','Insuffisant',True)
    after=action_professional_eligibility(e,aid,p)
    assert not after['eligible'] and after['status']=='NIVEAU_INSUFFISANT'

def test_exception_assignment_remains_distinct_and_motivated(tmp_path):
    e,aid,p,svc=_setup(tmp_path)
    ok,msg=assign_action_professional(e,aid,p,'admin@test',allow_exception=True,reason=None)
    assert not ok and 'justification' in msg.lower()
    ok,msg=assign_action_professional(e,aid,p,'admin@test',allow_exception=True,reason='Décision responsable pédagogique')
    assert ok
    assert not action_professional_eligibility(e,aid,p)['eligible']
