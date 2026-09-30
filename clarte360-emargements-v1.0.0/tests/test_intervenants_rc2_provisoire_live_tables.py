from db import make_engine, init_db, one
from services import *

def eng(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'x.db')); init_db(e); return e

def test_unused_candidate_can_be_physically_deleted(tmp_path):
    e=eng(tmp_path); p=create_professional_candidate(e,'Test Candidate','candidate@example.test',actor='admin')
    assert professional_delete_dependencies(e,p)==[]
    assert delete_professional_if_unused(e,p,'admin') is True
    assert one(e,'SELECT * FROM professional_persons WHERE professional_person_id=:p',{'p':p}) is None

def test_used_intervenant_is_inactivated_not_physically_deleted(tmp_path):
    e=eng(tmp_path); p=create_professional_intervenant(e,'Test Intervenant','intervenant@example.test',actor='admin')
    add_professional_experience(e,p,'Consultant',actor='admin')
    assert professional_delete_dependencies(e,p)
    try: delete_professional_if_unused(e,p,'admin'); assert False
    except ValueError: pass
    assert set_professional_active(e,p,False,'admin') is True
    assert int(one(e,'SELECT active FROM professional_persons WHERE professional_person_id=:p',{'p':p})['active'])==0

def test_structured_row_update_and_delete(tmp_path):
    e=eng(tmp_path); p=create_professional_candidate(e,'Table Test','table@example.test',actor='admin')
    rid=add_professional_experience(e,p,'Ancien poste','Org',actor='admin')
    update_professional_structured_row(e,'professional_experiences',rid,p,{'role_title':'Nouveau poste'},'admin')
    assert one(e,'SELECT role_title FROM professional_experiences WHERE id=:i',{'i':rid})['role_title']=='Nouveau poste'
    delete_professional_structured_row(e,'professional_experiences',rid,p,'admin')
    assert one(e,'SELECT id FROM professional_experiences WHERE id=:i',{'i':rid}) is None

def test_rc21_version_and_live_table_ui():
    import branding
    assert branding.APP_VERSION=='3.0.0-INTERVENANTS-RC2-1'
    src=open('app.py',encoding='utf-8').read()
    assert 'Gérer un dossier de la liste' in src
    assert 'Ouvrir / étudier' in src
    assert 'Modifier ou supprimer une ligne du tableau' in src
