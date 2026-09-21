from db import make_engine, init_db, q, one
from services import (create_professional_candidate,update_professional_profile,store_professional_document,
 candidate_completeness,set_candidate_work_status,request_candidate_complement,resolve_candidate_request,
 decide_candidate,candidate_workflow_history)
import pytest


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e


def complete(e,ppid,email='candidate@example.test'):
    update_professional_profile(e,ppid,{'title':'Camille Exemple','email':email,'collaboration_type':'INDEPENDANT'},'admin@test')
    store_professional_document(e,ppid,b'%PDF-1.4 test','cv.pdf','CV','admin@test')


def test_candidate_stays_non_operational_until_human_validation():
    e=eng(); p=create_professional_candidate(e,'Camille Exemple','candidate@example.test',actor='admin@test')
    pp=one(e,'SELECT * FROM professional_persons WHERE professional_person_id=:p',{'p':p})
    assert pp['principal_status']=='CANDIDAT' and pp['trainer_id'] is None
    assert one(e,'SELECT * FROM trainers WHERE professional_person_id=:p',{'p':p}) is None


def test_completeness_and_ready_decision_guard():
    e=eng(); p=create_professional_candidate(e,'Camille Exemple','candidate@example.test',actor='admin@test')
    assert not candidate_completeness(e,p)['complete']
    with pytest.raises(ValueError): set_candidate_work_status(e,p,'PRET_DECISION','admin@test')
    complete(e,p); assert candidate_completeness(e,p)['complete']
    set_candidate_work_status(e,p,'PRET_DECISION','admin@test')
    assert one(e,'SELECT candidate_work_status FROM professional_persons WHERE professional_person_id=:p',{'p':p})['candidate_work_status']=='PRET_DECISION'


def test_complement_request_is_historized_and_resolvable():
    e=eng(); p=create_professional_candidate(e,'Camille Exemple','candidate@example.test',actor='admin@test')
    rid=request_candidate_complement(e,p,'Merci de joindre votre CV.','admin@test')
    assert one(e,'SELECT status FROM candidate_requests WHERE id=:i',{'i':rid})['status']=='OUVERTE'
    resolve_candidate_request(e,rid,'admin@test','CV reçu')
    assert one(e,'SELECT status FROM candidate_requests WHERE id=:i',{'i':rid})['status']=='RESOLUE'
    assert candidate_workflow_history(e,p)


def test_validation_keeps_same_professional_person_id_and_creates_operational_link():
    e=eng(); p=create_professional_candidate(e,'Camille Exemple','candidate@example.test',actor='admin@test'); complete(e,p)
    decide_candidate(e,p,'VALIDER','admin@test','Dossier vérifié')
    pp=one(e,'SELECT * FROM professional_persons WHERE professional_person_id=:p',{'p':p})
    tr=one(e,'SELECT * FROM trainers WHERE id=:i',{'i':pp['trainer_id']})
    assert pp['principal_status']=='INTERVENANT' and pp['candidate_work_status']=='VALIDE'
    assert tr['professional_person_id']==p
    assert len(q(e,'SELECT * FROM professional_persons WHERE professional_person_id=:p',{'p':p}))==1


def test_refusal_does_not_create_intervenant():
    e=eng(); p=create_professional_candidate(e,'Camille Exemple','candidate@example.test',actor='admin@test')
    decide_candidate(e,p,'REFUSER','admin@test','Profil non retenu')
    pp=one(e,'SELECT * FROM professional_persons WHERE professional_person_id=:p',{'p':p})
    assert pp['principal_status']=='CANDIDAT' and pp['candidate_work_status']=='REFUSE' and pp['trainer_id'] is None
