from db import make_engine, init_db
from services import (create_professional_intervenant,create_professional_candidate,list_services,add_service_criterion,
 set_human_service_qualification,set_human_criterion_assessment,collective_qualification_matrix,search_qualified_professionals,
 save_ai_qualification_proposal)
from qualification_ai import PROMPT_VERSION

def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e

def test_collective_matrix_uses_human_validation_not_ai_proposal():
    e=eng(); s=list_services(e,True)[0]; p=create_professional_intervenant(e,'Alpha',actor='admin')
    save_ai_qualification_proposal(e,p,s['id'],{'service_level':4,'confidence':.9,'rationale':'x','evidence':[],'missing_points':[],'criteria':[]},'admin','openai','test',PROMPT_VERSION,'h')
    row=[x for x in collective_qualification_matrix(e) if x['professional_person_id']==p and x['service_id']==s['id']][0]
    assert row['human_value'] is None and row['ai_value']==4

def test_search_returns_only_human_qualified_active_intervenants():
    e=eng(); s=list_services(e,True)[0]
    p1=create_professional_intervenant(e,'Bravo',actor='admin'); p2=create_professional_intervenant(e,'Alpha',actor='admin')
    set_human_service_qualification(e,p1,s['id'],3,'admin'); set_human_service_qualification(e,p2,s['id'],2,'admin')
    out=search_qualified_professionals(e,s['id'],3)
    assert [x['professional_person_id'] for x in out]==[p1]

def test_candidates_excluded_by_default_but_can_be_included():
    e=eng(); s=list_services(e,True)[0]; p=create_professional_candidate(e,'Candidate',actor='admin')
    set_human_service_qualification(e,p,s['id'],4,'admin')
    assert not any(x['professional_person_id']==p for x in collective_qualification_matrix(e))
    assert any(x['professional_person_id']==p for x in collective_qualification_matrix(e,include_candidates=True))

def test_required_criteria_filter_is_available():
    e=eng(); s=list_services(e,True)[0]; p=create_professional_intervenant(e,'Charlie',actor='admin')
    c=add_service_criterion(e,s['id'],'MET','METIER_TECHNIQUE','Critere requis',required=True,minimum_level=3,actor='admin')
    set_human_service_qualification(e,p,s['id'],4,'admin'); set_human_criterion_assessment(e,p,c,2,'admin')
    assert len(search_qualified_professionals(e,s['id'],3,False))==1
    assert len(search_qualified_professionals(e,s['id'],3,True))==0

def test_matrix_has_one_projection_row_per_person_and_active_service():
    e=eng(); create_professional_intervenant(e,'Delta',actor='admin'); create_professional_intervenant(e,'Echo',actor='admin')
    assert len(collective_qualification_matrix(e))==2*len(list_services(e,True))
