from pathlib import Path
from db import make_engine, init_db, one
from services import (
    create_action, add_participant, create_beneficiary_from_participant,
    find_beneficiary_candidates, link_participant_to_beneficiary,
    create_beneficiary_portal_invitation, accept_beneficiary_invitation,
    verify_beneficiary_login, update_beneficiary_email,
    store_document, list_beneficiary_documents, beneficiary_portal_zip,
    delete_document_reference, document_storage_stats,
)

def engine(tmp_path):
    e=make_engine(f"sqlite:///{tmp_path/'db.sqlite'}");init_db(e);return e

def action(e,no='CLA9001'):
    return create_action(e,{'action_no':no,'title':'Test','subtitle':None,'nature':'FORMATION','mode':'INTRA','client_name':'Client','client_type':'ENTREPRISE','group_code':None,'planned_hours':7,'expected_participants':1,'admin_email':'admin@test.fr','trainer_name':None,'trainer_email':None,'location':'Paris','notes':None,'source':'TEST'},'admin@test.fr')

def participant(e,aid,last='PAQUETTE',first='Quentin',email='quentin@example.fr'):
    pid,_=add_participant(e,aid,{'individual_action_no':None,'last_name':last,'birth_name':None,'first_name':first,'birth_date':'1990-02-03','email':email,'employee_id':None,'company_name':'Client','phone':None},'admin@test.fr');return pid

def test_permanent_beneficiary_link_and_candidate(tmp_path):
    e=engine(tmp_path);a=action(e);p=participant(e,a)
    bid=create_beneficiary_from_participant(e,p,'admin@test.fr')
    assert one(e,'SELECT beneficiary_id FROM participants WHERE id=:p',{'p':p})['beneficiary_id']==bid
    cand=find_beneficiary_candidates(e,'POQUETTE','Quentin','1990-02-03')
    assert cand and cand[0]['id']==bid and cand[0]['match_score']>=68

def test_no_automatic_merge_possible(tmp_path):
    e=engine(tmp_path);a1=action(e,'CLA9002');p1=participant(e,a1);bid=create_beneficiary_from_participant(e,p1)
    a2=action(e,'CLA9003');p2=participant(e,a2,last='POQUETTE')
    assert one(e,'SELECT beneficiary_id FROM participants WHERE id=:p',{'p':p2})['beneficiary_id'] is None
    assert find_beneficiary_candidates(e,'POQUETTE','Quentin','1990-02-03')[0]['id']==bid

def test_portal_invitation_login_and_email_change(tmp_path):
    e=engine(tmp_path);a=action(e);p=participant(e,a);bid=create_beneficiary_from_participant(e,p)
    tok=create_beneficiary_portal_invitation(e,bid,'quentin@example.fr','admin@test.fr')
    ok,msg=accept_beneficiary_invitation(e,tok,'MotDePasse!2026');assert ok,msg
    acc=verify_beneficiary_login(e,'quentin@example.fr','MotDePasse!2026');assert acc and acc['beneficiary_id']==bid
    change_token=update_beneficiary_email(e,bid,'nouveau@example.fr','admin@test.fr')
    assert verify_beneficiary_login(e,'nouveau@example.fr','MotDePasse!2026') is None
    assert verify_beneficiary_login(e,'quentin@example.fr','MotDePasse!2026')
    ok,msg=accept_beneficiary_invitation(e,change_token,'MotDePasse!2026');assert ok,msg
    assert verify_beneficiary_login(e,'nouveau@example.fr','MotDePasse!2026')
    assert one(e,'SELECT id FROM beneficiaries WHERE id=:b',{'b':bid})

def test_sha256_dedup_across_actions(tmp_path, monkeypatch):
    import services
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'blobs');services.BENEFICIARY_DOC_DIR.mkdir()
    e=engine(tmp_path);a1=action(e,'CLA9004');a2=action(e,'CLA9005');data=b'meme contenu strictement identique'
    r1,h1,d1=store_document(e,data,'Support A.pdf','COURS','admin',action_id=a1)
    r2,h2,d2=store_document(e,data,'Support B.pdf','COURS','admin',action_id=a2)
    st=document_storage_stats(e)
    assert h1==h2 and d1 is False and d2 is True
    assert st['files']==1 and st['references']==2

def test_action_document_visible_in_linked_beneficiary_portal(tmp_path, monkeypatch):
    import services
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'blobs');services.BENEFICIARY_DOC_DIR.mkdir()
    e=engine(tmp_path);a=action(e,'CLA9006');p=participant(e,a);bid=create_beneficiary_from_participant(e,p)
    store_document(e,b'cours','Cours module 2.pdf','COURS','admin',action_id=a,audience='ACTION_BENEFICIARIES')
    docs=list_beneficiary_documents(e,bid)
    assert len(docs)==1 and docs[0]['display_name']=='Cours module 2.pdf'

def test_portal_zip_contains_documents(tmp_path, monkeypatch):
    import services, zipfile, io
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'blobs');services.BENEFICIARY_DOC_DIR.mkdir()
    e=engine(tmp_path);a=action(e,'CLA9007');p=participant(e,a);bid=create_beneficiary_from_participant(e,p)
    store_document(e,b'abc','Support.pdf','COURS','admin',action_id=a)
    raw=beneficiary_portal_zip(e,bid)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert 'CLA9007/Support.pdf' in z.namelist();assert z.read('CLA9007/Support.pdf')==b'abc'

def test_physical_file_removed_only_after_last_reference(tmp_path, monkeypatch):
    import services
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'blobs');services.BENEFICIARY_DOC_DIR.mkdir()
    e=engine(tmp_path);a1=action(e,'CLA9008');a2=action(e,'CLA9009')
    r1,h,_=store_document(e,b'xyz','A.pdf','COURS','admin',action_id=a1);r2,_,_=store_document(e,b'xyz','B.pdf','COURS','admin',action_id=a2)
    sf=one(e,'SELECT * FROM stored_files WHERE sha256=:h',{'h':h});path=Path(sf['storage_path']);assert path.exists()
    assert delete_document_reference(e,r1,'admin');assert path.exists()
    assert delete_document_reference(e,r2,'admin');assert not path.exists();assert one(e,'SELECT * FROM stored_files WHERE sha256=:h',{'h':h}) is None
