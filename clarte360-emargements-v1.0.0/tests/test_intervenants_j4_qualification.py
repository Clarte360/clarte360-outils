import pytest
from db import make_engine, init_db, one
from services import (
    create_professional_candidate, create_professional_intervenant,
    list_services, add_service_criterion, set_human_service_qualification,
    set_human_criterion_assessment, add_qualification_evidence,
    get_person_service_qualification, list_person_service_qualifications,
    qualification_adequacy_summary, delete_service
)


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e


def service(e):
    return list_services(e,active_only=True)[0]


def test_manual_service_qualification_works_for_candidate_and_intervenant():
    e=eng(); s=service(e)
    c=create_professional_candidate(e,'Candidate Exemple','candidate@example.test',actor='admin@test')
    i=create_professional_intervenant(e,'Intervenant Exemple','intervenant@example.test',actor='admin@test')
    set_human_service_qualification(e,c,s['id'],2,'admin@test','Expérience partielle',True)
    set_human_service_qualification(e,i,s['id'],3,'admin@test','Autonome',True)
    assert get_person_service_qualification(e,c,s['id'])['qualification']['human_value']==2
    assert get_person_service_qualification(e,i,s['id'])['qualification']['human_value']==3


def test_human_validation_is_locked_and_historized():
    e=eng(); s=service(e); p=create_professional_intervenant(e,'Alex Exemple',actor='admin@test')
    set_human_service_qualification(e,p,s['id'],3,'admin@test','Validation initiale',True,'2027-09-20')
    set_human_service_qualification(e,p,s['id'],4,'admin@test','Réévaluation humaine',True,'2028-09-20')
    q=get_person_service_qualification(e,p,s['id'])
    assert q['qualification']['human_value']==4 and q['qualification']['human_locked']==1
    assert q['qualification']['review_due_at']=='2028-09-20'
    events=[x for x in q['history'] if x['event_type']=='SERVICE_HUMAN_VALIDATION']
    assert len(events)==2 and events[0]['old_human_value']==3 and events[0]['new_human_value']==4


def test_criterion_assessment_computes_required_adequacy():
    e=eng(); s=service(e); p=create_professional_intervenant(e,'Sam Exemple',actor='admin@test')
    c1=add_service_criterion(e,s['id'],'METIER','METIER_TECHNIQUE','Maîtriser le domaine',required=True,minimum_level=3,actor='admin@test')
    c2=add_service_criterion(e,s['id'],'PEDA','PEDAGOGIQUE','Structurer une intervention',required=True,minimum_level=2,actor='admin@test')
    set_human_criterion_assessment(e,p,c1,3,'admin@test','Démontré',True)
    set_human_criterion_assessment(e,p,c2,1,'admin@test','À renforcer',True)
    x=qualification_adequacy_summary(e,p,s['id'])
    assert x['criteria_total']==2 and x['criteria_assessed']==2
    assert x['required_total']==2 and x['required_ok']==1 and not x['required_complete']


def test_evidence_can_be_recorded_without_ai_and_blocks_service_deletion():
    e=eng(); s=service(e); p=create_professional_intervenant(e,'Lou Exemple',actor='admin@test')
    eid=add_qualification_evidence(e,p,s['id'],'admin@test','EXPERIENCE','10 ans de pratique documentée')
    assert one(e,'SELECT * FROM qualification_evidence WHERE id=:i',{'i':eid})['evidence_type']=='EXPERIENCE'
    with pytest.raises(ValueError): delete_service(e,s['id'],'admin@test')


def test_individual_matrix_lists_all_active_services_and_validates_review_date():
    e=eng(); p=create_professional_intervenant(e,'Mina Exemple',actor='admin@test')
    rows=list_person_service_qualifications(e,p,True)
    assert len(rows)==len(list_services(e,active_only=True))
    with pytest.raises(ValueError): set_human_service_qualification(e,p,rows[0]['service_id'],3,'admin@test',review_due_at='20/09/2027')
