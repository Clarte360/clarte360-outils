from db import make_engine, init_db, one
from services import (create_professional_intervenant, update_professional_profile, list_services,
 set_human_service_qualification, professional_cv_status, professional_cv_source_sha256,
 record_professional_cv_generation, professional_cv_history)

def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e

def person(e):
    p=create_professional_intervenant(e,'Alice Martin','alice@example.test','0600000000','SOUS_TRAITANT','admin')
    update_professional_profile(e,p,{'title':'Consultante QSE','summary':'Initial','email':'alice@example.test'},'admin')
    return p

def test_p6_cv_reports_regeneration_when_published_source_changes():
    e=eng(); p=person(e)
    assert professional_cv_status(e,p,'CLIENT')['status']=='JAMAIS_GENERE'
    record_professional_cv_generation(e,p,'CLIENT','cv.pdf',b'pdf-v1','admin')
    assert professional_cv_status(e,p,'CLIENT')['status']=='A_JOUR'
    update_professional_profile(e,p,{'summary':'Résumé modifié'},'admin')
    assert professional_cv_status(e,p,'CLIENT')['status']=='A_REGENERER'

def test_p6_internal_only_change_does_not_dirty_client_cv():
    e=eng(); p=person(e)
    record_professional_cv_generation(e,p,'CLIENT','cv.pdf',b'pdf-v1','admin')
    update_professional_profile(e,p,{'title':'Consultante QSE','summary':'Initial','email':'alice@example.test','notes_internal':'Confidentiel'},'admin')
    assert professional_cv_status(e,p,'CLIENT')['status']=='A_JOUR'
    assert professional_cv_status(e,p,'INTERNE')['status']=='JAMAIS_GENERE'

def test_p6_human_qualification_changes_client_source_but_ai_only_does_not():
    e=eng(); p=person(e); s=list_services(e,True)[0]
    before=professional_cv_source_sha256(e,p,'CLIENT')
    from db import execute
    execute(e,'INSERT INTO person_service_qualifications(professional_person_id,service_id,ai_value,ai_confidence,created_at,updated_at) VALUES(:p,:s,4,0.99,:n,:n)',{'p':p,'s':s['id'],'n':'2026-10-02T00:00:00+00:00'})
    assert professional_cv_source_sha256(e,p,'CLIENT')==before
    set_human_service_qualification(e,p,s['id'],3,'admin','Validé')
    assert professional_cv_source_sha256(e,p,'CLIENT')!=before

def test_p6_identical_generation_is_idempotent():
    e=eng(); p=person(e)
    assert record_professional_cv_generation(e,p,'CLIENT','cv.pdf',b'same','admin')==1
    assert record_professional_cv_generation(e,p,'CLIENT','cv.pdf',b'same','admin')==1
    assert len(professional_cv_history(e,p))==1

def test_p6_schema_migrates_existing_cv_history_additively():
    e=eng(); cols={r['name'] for r in __import__('db').q(e,'PRAGMA table_info(professional_cv_generations)')}
    assert 'source_sha256' in cols
