from datetime import date, timedelta
from db import make_engine, init_db
from services import (create_professional_intervenant,list_services,collective_qualification_matrix,
    set_human_service_qualification,create_qualification_review_point)

def eng():
    e=make_engine('sqlite:///:memory:');init_db(e);return e

def _row(e,p,s):
    return next(x for x in collective_qualification_matrix(e) if x['professional_person_id']==p and x['service_id']==s)

def test_p4_non_evaluee_and_human_validated_status():
    e=eng();p=create_professional_intervenant(e,'Pilotage P4',actor='admin');s=list_services(e,True)[0]['id']
    assert _row(e,p,s)['management_status']=='NON_EVALUEE'
    set_human_service_qualification(e,p,s,3,'admin','validé')
    assert _row(e,p,s)['management_status']=='QUALIFICATION_VALIDEE'

def test_p4_open_point_is_management_priority():
    e=eng();p=create_professional_intervenant(e,'Points P4',actor='admin');s=list_services(e,True)[0]['id']
    create_qualification_review_point(e,p,s,'Justificatif à contrôler','admin')
    r=_row(e,p,s);assert r['management_status']=='POINTS_OUVERTS';assert r['open_points_count']==1

def test_p4_expired_review_has_priority():
    e=eng();p=create_professional_intervenant(e,'Revision P4',actor='admin');s=list_services(e,True)[0]['id']
    set_human_service_qualification(e,p,s,4,'admin','ok',review_due_at=(date.today()-timedelta(days=1)).isoformat())
    assert _row(e,p,s)['management_status']=='REVISION_ECHUE'

def test_p4_ui_is_actionable_and_hides_ai_technical_columns():
    src=open('app.py',encoding='utf-8').read()
    assert 'Qualifications & pilotage DRH' in src
    assert 'Ouvrir le dossier sur cette qualification' in src
    assert "st.session_state['_rc222_dossier_screen']='Qualifications'" in src
    block=src[src.index('with sub_matrix:'):src.index('with sub_prestations:')]
    assert "'Confiance analyse'" not in block and "'Critères IA'" not in block
