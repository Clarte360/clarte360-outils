from pathlib import Path
from db import make_engine, init_db, one
from services import (create_professional_candidate,get_professional_360,update_professional_profile,
 add_professional_experience,add_professional_education,add_professional_certification,
 add_professional_language,add_professional_specialty,store_professional_document)

def eng(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'j2.db'));init_db(e);return e

def test_candidate_is_unique_professional_person_and_not_trainer(tmp_path):
    e=eng(tmp_path);p=create_professional_candidate(e,'Alice Exemple','alice@example.org','0600000000',actor='admin')
    x=get_professional_360(e,p);assert x['principal_status']=='CANDIDAT';assert x['trainer_id'] is None
    assert one(e,'SELECT COUNT(*) n FROM trainers')['n']==0

def test_professional_360_structured_sections(tmp_path):
    e=eng(tmp_path);p=create_professional_candidate(e,'Bob Exemple',actor='admin')
    update_professional_profile(e,p,{'title':'Consultant formateur','collaboration_type':'INDEPENDANT','city':'Paris','country':'France'},'admin')
    add_professional_experience(e,p,'Responsable QHSE','Entreprise X',description='Pilotage',actor='admin')
    add_professional_education(e,p,'Master QHSE','Université','QHSE',actor='admin')
    add_professional_certification(e,p,'Auditeur','CERTIFICATION','Organisme',actor='admin')
    add_professional_language(e,p,'Anglais','C1','Certification','admin');add_professional_specialty(e,p,'QHSE',actor='admin')
    x=get_professional_360(e,p);assert x['city']=='Paris';assert len(x['experiences'])==1;assert len(x['education'])==1;assert len(x['certifications'])==1;assert len(x['languages'])==1;assert len(x['specialties'])==1

def test_professional_documents_use_shared_blob_store(tmp_path):
    e=eng(tmp_path);p=create_professional_candidate(e,'Claire Exemple',actor='admin')
    d1=store_professional_document(e,p,b'%PDF-1.4 test','cv.pdf','CV','admin')
    d2=store_professional_document(e,p,b'%PDF-1.4 test','cv-copie.pdf','CV','admin')
    assert d1!=d2;assert one(e,'SELECT COUNT(*) n FROM stored_files')['n']==1
    assert len(get_professional_360(e,p)['documents'])==2
