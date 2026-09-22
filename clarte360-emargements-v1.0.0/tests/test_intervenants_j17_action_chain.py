from db import make_engine,init_db,execute,utcnow_iso
from services import (create_professional_intervenant,list_services,set_action_service_requirement,
 set_human_service_qualification,assign_action_professional,action_assigned_professional_statuses,
 find_service_matches,professional_person_for_trainer,action_professional_eligibility)

def eng(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'j17.db'));init_db(e);return e

def action(e,no='A-J17'):
    n=utcnow_iso();return execute(e,"INSERT INTO actions(action_no,title,nature,mode,status,created_at,updated_at) VALUES(:no,'Action J17','FORMATION','PRESENTIEL','BROUILLON',:n,:n)",{'no':no,'n':n})

def test_assigned_unqualified_status_remains_visible_after_exception(tmp_path):
    e=eng(tmp_path);a=action(e);svc=list_services(e,True)[0]
    p=create_professional_intervenant(e,'Non Qualifie J17',actor='admin')
    set_action_service_requirement(e,a,svc['id'],'admin',3,False)
    ok,msg=assign_action_professional(e,a,p,'admin',reason='Essai contrôlé',allow_exception=True)
    assert ok
    rows=action_assigned_professional_statuses(e,a)
    assert len(rows)==1 and rows[0]['professional_person_id']==p
    assert rows[0]['eligibility_status']=='NON_QUALIFIE' and not rows[0]['eligible']
    assert 'Aucune qualification humaine' in rows[0]['eligibility_reason']

def test_assigned_person_recalculates_to_qualified_after_human_validation(tmp_path):
    e=eng(tmp_path);a=action(e);svc=list_services(e,True)[0]
    p=create_professional_intervenant(e,'Qualifie J17',actor='admin')
    set_action_service_requirement(e,a,svc['id'],'admin',3,False)
    assign_action_professional(e,a,p,'admin',reason='Essai contrôlé',allow_exception=True)
    assert action_assigned_professional_statuses(e,a)[0]['eligibility_status']=='NON_QUALIFIE'
    set_human_service_qualification(e,p,svc['id'],3,'admin','Décision humaine',True)
    row=action_assigned_professional_statuses(e,a)[0]
    assert row['eligibility_status']=='QUALIFIE' and row['eligible'] and row['human_value']==3

def test_assigned_insufficient_level_is_explicit(tmp_path):
    e=eng(tmp_path);a=action(e);svc=list_services(e,True)[0]
    p=create_professional_intervenant(e,'Niveau Deux J17',actor='admin')
    set_action_service_requirement(e,a,svc['id'],'admin',3,False)
    set_human_service_qualification(e,p,svc['id'],2,'admin','Niveau partiel',True)
    assign_action_professional(e,a,p,'admin',reason='Exception documentée',allow_exception=True)
    row=action_assigned_professional_statuses(e,a)[0]
    assert row['eligibility_status']=='NIVEAU_INSUFFISANT' and '2/4' in row['eligibility_reason'] and '3/4' in row['eligibility_reason']

def test_no_requirement_never_claims_qualification(tmp_path):
    e=eng(tmp_path);a=action(e);p=create_professional_intervenant(e,'Sans Prestation J17',actor='admin')
    ev=action_professional_eligibility(e,a,p)
    assert ev['status']=='A_VERIFIER' and ev['eligible']
    assert 'Aucune prestation' in ev['reason']

def test_trainer_bridge_and_catalogue_suggestions(tmp_path):
    e=eng(tmp_path);p=create_professional_intervenant(e,'Bridge J17',actor='admin')
    from db import one
    tr=one(e,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':p})
    assert professional_person_for_trainer(e,tr['trainer_id'])['professional_person_id']==p
    services=list_services(e,True)
    target=services[0]
    matches=find_service_matches(e,target['name'],5)
    assert matches and matches[0]['id']==target['id']
