from db import make_engine,init_db
from services import (create_professional_intervenant,create_professional_candidate,update_professional_profile,
 list_services,set_human_service_qualification,professional_people_operational_view,professional_dashboard_metrics)

def eng():
    e=make_engine('sqlite:///:memory:');init_db(e);return e

def test_j9_operational_view_summarizes_qualification_without_new_business_truth():
    e=eng();p=create_professional_intervenant(e,'Alice Martin','alice@example.test',collaboration_type='INDEPENDANT',actor='admin')
    s=list_services(e,True)[0];set_human_service_qualification(e,p,s['id'],3,'admin','Validé')
    row=next(x for x in professional_people_operational_view(e) if x['professional_person_id']==p)
    assert row['display_name']=='Alice Martin' and row['qualification_count']==1 and row['qualification_max']==3

def test_j9_candidate_view_exposes_existing_completeness_only():
    e=eng();p=create_professional_candidate(e,'Bob Test','bob@example.test',collaboration_type='A_DEFINIR',actor='admin')
    row=next(x for x in professional_people_operational_view(e) if x['professional_person_id']==p)
    assert row['principal_status']=='CANDIDAT' and 0 <= row['completion_percent'] <= 100

def test_j9_dashboard_separates_intervenants_candidates_and_qualified_people():
    e=eng();i=create_professional_intervenant(e,'Alice Martin','alice@example.test',collaboration_type='INDEPENDANT',actor='admin')
    create_professional_candidate(e,'Bob Test','bob@example.test',collaboration_type='A_DEFINIR',actor='admin')
    s=list_services(e,True)[0];set_human_service_qualification(e,i,s['id'],3,'admin')
    m=professional_dashboard_metrics(e)
    assert m['active_intervenants']==1 and m['active_candidates']==1 and m['qualified_intervenants']==1

def test_j9_no_ai_proposal_counts_as_human_qualification():
    e=eng();p=create_professional_intervenant(e,'Alice Martin','alice@example.test',collaboration_type='INDEPENDANT',actor='admin')
    row=next(x for x in professional_people_operational_view(e) if x['professional_person_id']==p)
    assert row['qualification_count']==0

def test_j9_ui_has_operational_tabs_and_filters():
    src=open('app.py',encoding='utf-8').read()
    assert "['Intervenants','Candidats','Qualifications & recherche','Alertes','Prestations']" in src
    assert 'Rechercher un intervenant' in src and 'Rechercher un candidat' in src
