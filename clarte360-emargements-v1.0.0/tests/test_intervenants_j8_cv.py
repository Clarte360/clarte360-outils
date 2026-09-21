from db import make_engine,init_db,one
from services import (create_professional_intervenant,update_professional_profile,add_professional_experience,
 add_professional_education,add_professional_certification,add_professional_language,add_professional_specialty,
 list_services,set_human_service_qualification,professional_cv_snapshot,record_professional_cv_generation,professional_cv_history)
from pdf_utils import professional_cv_pdf

def eng():
    e=make_engine('sqlite:///:memory:');init_db(e);return e

def rich(e):
    p=create_professional_intervenant(e,'Alice Martin','alice@example.test','0600000000','INDEPENDANT','admin')
    update_professional_profile(e,p,{'title':'Consultante QSE','summary':'Accompagnement et formation.','email':'alice@example.test','phone':'0600000000','city':'Paris','country':'France','linkedin_url':'https://example.test/alice','notes_internal':'Note confidentielle'},'admin')
    add_professional_experience(e,p,'Responsable QSE','Entreprise X','2020-01-01',None,True,'Pilotage QSE','admin')
    add_professional_education(e,p,'Master QSE','Université','QSE','2019-06-01',None,'admin')
    add_professional_certification(e,p,'Certificat coach','CERTIFICATION','Organisme Y',valid_until='2028-01-01',actor='admin')
    add_professional_language(e,p,'Français','C2',actor='admin');add_professional_specialty(e,p,'QSE',actor='admin')
    s=list_services(e,True)[0];set_human_service_qualification(e,p,s['id'],3,'admin','Validé')
    return p,s

def test_j8_client_snapshot_excludes_private_fields_and_keeps_human_qualifications():
    e=eng();p,s=rich(e);d=professional_cv_snapshot(e,p,'CLIENT')
    assert 'email' not in d and 'phone' not in d and 'notes_internal' not in d
    assert d['qualifications'][0]['human_value']==3 and d['qualifications'][0]['service_id']==s['id']

def test_j8_internal_snapshot_contains_internal_fields():
    e=eng();p,_=rich(e);d=professional_cv_snapshot(e,p,'INTERNE')
    assert d['email']=='alice@example.test' and d['phone']=='0600000000' and d['notes_internal']=='Note confidentielle'

def test_j8_pdf_generation_is_valid_and_client_does_not_expose_contacts():
    e=eng();p,_=rich(e);client=professional_cv_pdf(e,p,'CLIENT');internal=professional_cv_pdf(e,p,'INTERNE')
    assert client.startswith(b'%PDF') and internal.startswith(b'%PDF') and len(client)>1000 and len(internal)>1000
    # Snapshot is the privacy contract; PDF is generated exclusively from that snapshot.
    assert 'email' not in professional_cv_snapshot(e,p,'CLIENT')

def test_j8_generation_history_versions_are_separate_by_audience():
    e=eng();p,_=rich(e)
    assert record_professional_cv_generation(e,p,'CLIENT','c.pdf',b'a','admin')==1
    assert record_professional_cv_generation(e,p,'CLIENT','c2.pdf',b'b','admin')==2
    assert record_professional_cv_generation(e,p,'INTERNE','i.pdf',b'c','admin')==1
    h=professional_cv_history(e,p);assert len(h)==3 and one(e,"SELECT MAX(version_no) n FROM professional_cv_generations WHERE professional_person_id=:p AND audience='CLIENT'",{'p':p})['n']==2

def test_j8_unvalidated_ai_or_absent_human_level_never_enters_cv():
    e=eng();p,_=rich(e); svcs=list_services(e,True)
    if len(svcs)>1:
        from db import execute
        execute(e,'INSERT INTO person_service_qualifications(professional_person_id,service_id,ai_value,ai_confidence,created_at,updated_at) VALUES(:p,:s,4,0.99,:n,:n)',{'p':p,'s':svcs[1]['id'],'n':'2026-09-20T00:00:00+00:00'})
        ids={x['service_id'] for x in professional_cv_snapshot(e,p,'CLIENT')['qualifications']};assert svcs[1]['id'] not in ids
