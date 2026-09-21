from db import make_engine, init_db, one
from services import create_professional_intervenant, create_professional_candidate
import pytest


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e


def test_direct_intervenant_creation_skips_candidate_workflow_and_keeps_one_person():
    e=eng()
    p=create_professional_intervenant(e,'Alex Exemple','alex@example.test','0600000000','INDEPENDANT','admin@test')
    pp=one(e,'SELECT * FROM professional_persons WHERE professional_person_id=:p',{'p':p})
    tr=one(e,'SELECT * FROM trainers WHERE id=:i',{'i':pp['trainer_id']})
    prof=one(e,'SELECT * FROM professional_profiles WHERE professional_person_id=:p',{'p':p})
    assert pp['principal_status']=='INTERVENANT'
    assert pp['candidate_work_status']=='VALIDE'
    assert pp['active']==1
    assert tr['professional_person_id']==p
    assert prof['origin']=='ADMIN_DIRECT_INTERVENANT'
    assert one(e,'SELECT COUNT(*) n FROM candidate_workflow_events WHERE professional_person_id=:p',{'p':p})['n']==0
    assert one(e,'SELECT COUNT(*) n FROM candidate_decisions WHERE professional_person_id=:p',{'p':p})['n']==0


def test_direct_intervenant_creation_is_audited_and_status_historized():
    e=eng()
    p=create_professional_intervenant(e,'Sam Exemple',actor='admin@test')
    h=one(e,'SELECT * FROM professional_person_status_history WHERE professional_person_id=:p ORDER BY id DESC',{'p':p})
    assert h['new_principal_status']=='INTERVENANT'
    assert h['new_work_status']=='VALIDE'
    assert 'directe' in h['reason'].lower()


def test_direct_intervenant_refuses_duplicate_email_against_existing_professional_person():
    e=eng()
    create_professional_candidate(e,'Candidat Existant','same@example.test',actor='admin@test')
    with pytest.raises(ValueError):
        create_professional_intervenant(e,'Nouvel Intervenant','same@example.test',actor='admin@test')
