"""P1: autorisations documentaires côté service, refus inter-personnes et fuite client."""
from pathlib import Path
import io
import zipfile
import pytest
from db import make_engine, init_db, one, execute, utcnow_iso
from services import (
    create_action, add_participant, create_beneficiary_from_participant,
    store_document, store_document_for_actor, list_beneficiary_documents,
    list_action_documents, list_trainer_documents, list_admin_documents,
    read_document_for_actor, beneficiary_portal_zip, delete_document_reference,
    add_trainer, assign_action_trainer, unassign_action_trainer, participant_final_zip,
)


def setup(tmp_path, monkeypatch):
    import services
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'blobs')
    services.BENEFICIARY_DOC_DIR.mkdir()
    e=make_engine(f"sqlite:///{tmp_path/'p1.sqlite'}"); init_db(e)
    now=utcnow_iso()
    execute(e,"INSERT INTO admins(email,password_hash,role,active,created_at) VALUES('admin@test.fr','dummy','ADMIN',1,:d)",{'d':now})
    return e


def make_action(e,code='P1-1',nature='FORMATION'):
    return create_action(e,{'action_no':code,'title':'Essai P1','subtitle':None,'nature':nature,
        'mode':'INTRA','client_name':'Entreprise','client_type':'ENTREPRISE','group_code':None,
        'planned_hours':7,'expected_participants':2,'admin_email':'admin@test.fr',
        'trainer_name':None,'trainer_email':None,'location':'Paris','notes':None,'source':'TEST'},'admin@test.fr')


def make_person(e,aid,last):
    pid,_=add_participant(e,aid,{'last_name':last,'first_name':'Marie','birth_date':'1991-03-01',
        'email':last.lower()+'@example.fr','company_name':'Entreprise','phone':None},'admin@test.fr')
    return pid,create_beneficiary_from_participant(e,pid,'admin@test.fr')


def doc_names(e,bid):return {d['display_name'] for d in list_beneficiary_documents(e,bid)}


def test_one_collective_course_shared_only_with_own_action(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);p1,b1=make_person(e,a,'ONE');p2,b2=make_person(e,a,'TWO')
    other=make_action(e,'P1-2');_,b3=make_person(e,other,'THREE')
    store_document(e,b'cours','Cours.pdf','COURS','admin',action_id=a)
    assert doc_names(e,b1)=={'Cours.pdf'} and doc_names(e,b2)=={'Cours.pdf'}
    assert doc_names(e,b3)==set()
    assert len(list_action_documents(e,a))==1


def test_legacy_shared_label_never_leaks_individual_pip_report(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);p1,b1=make_person(e,a,'ONE');p2,b2=make_person(e,a,'TWO')
    ref,_,_=store_document(e,b'private-pip','PIP_prive.pdf','PIP_RIASEC_ONET','connector',
        action_id=a,beneficiary_id=b1,participant_id=p1,audience='ACTION_BENEFICIARIES')
    assert one(e,'SELECT audience FROM document_references WHERE id=:r',{'r':ref})['audience']=='BENEFICIARY_ONLY'
    assert doc_names(e,b1)=={'PIP_prive.pdf'}
    assert doc_names(e,b2)==set()
    assert read_document_for_actor(e,ref,'BENEFICIARY',b1)==b'private-pip'
    with pytest.raises(PermissionError):read_document_for_actor(e,ref,'BENEFICIARY',b2)
    with zipfile.ZipFile(io.BytesIO(beneficiary_portal_zip(e,b2))) as z:
        assert 'PIP_prive.pdf' not in ' '.join(z.namelist())


def test_historical_admin_document_not_visible_to_beneficiaries(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);_,b1=make_person(e,a,'ONE')
    ref,_,_=store_document(e,b'contract','Contrat_entreprise.pdf','ADMINISTRATIF','admin',action_id=a,
                          audience='ACTION_BENEFICIARIES',visible_to_beneficiary=True)
    assert doc_names(e,b1)==set()
    assert read_document_for_actor(e,ref,'ADMIN','admin@test.fr',action_id=a)==b'contract'
    with pytest.raises(PermissionError):read_document_for_actor(e,ref,'BENEFICIARY',b1)


def test_person_action_tuple_mismatch_fails_before_write(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a1=make_action(e);a2=make_action(e,'P1-2');p1,b1=make_person(e,a1,'ONE')
    with pytest.raises(ValueError,match='non inscrit'):
        store_document(e,b'bad','Other.pdf','BENEFICIAIRE','admin',action_id=a2,beneficiary_id=b1,audience='BENEFICIARY_ONLY')
    with pytest.raises(ValueError,match='hors action'):
        store_document(e,b'bad','Other.pdf','BENEFICIAIRE','admin',action_id=a2,participant_id=p1,audience='BENEFICIARY_ONLY')
    assert one(e,'SELECT count(*) n FROM document_references')['n']==0


def test_beneficiary_upload_cannot_target_peer(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);p1,b1=make_person(e,a,'ONE');p2,b2=make_person(e,a,'TWO')
    with pytest.raises(PermissionError):
        store_document_for_actor(e,'BENEFICIARY',b1,b'abc','My.pdf',a,beneficiary_id=b2,participant_id=p2)
    ref,_,_=store_document_for_actor(e,'BENEFICIARY',b1,b'abc','My.pdf',a,beneficiary_id=b1,participant_id=p1)
    assert doc_names(e,b1)=={'My.pdf'} and doc_names(e,b2)==set()
    assert read_document_for_actor(e,ref,'BENEFICIARY',b1)==b'abc'


def test_admin_categories_and_client_denial(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);p1,b1=make_person(e,a,'ONE')
    common,_,_=store_document_for_actor(e,'ADMIN','admin@test.fr',b'cours','Support.pdf',a,category='COURS')
    private,_,_=store_document_for_actor(e,'ADMIN','admin@test.fr',b'prive','Attestation.pdf',a,
        category='ADMINISTRATIF_INDIVIDUEL',beneficiary_id=b1,participant_id=p1)
    client,_,_=store_document_for_actor(e,'ADMIN','admin@test.fr',b'facture','Facture.pdf',a,category='CLIENT_CONTRACTUEL')
    assert doc_names(e,b1)=={'Support.pdf','Attestation.pdf'}
    assert read_document_for_actor(e,client,'ADMIN','admin@test.fr',action_id=a)==b'facture'
    with pytest.raises(PermissionError):read_document_for_actor(e,private,'ADMIN','admin@test.fr',action_id=a)
    with pytest.raises(PermissionError):read_document_for_actor(e,client,'BENEFICIARY',b1)
    for rid in (common,private,client):
        with pytest.raises(PermissionError):read_document_for_actor(e,rid,'CLIENT','hr@example.fr',action_id=a)


def test_trainer_must_be_assigned_and_referent_to_access_individual_reports(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);p1,b1=make_person(e,a,'ONE');p2,b2=make_person(e,a,'TWO')
    tr=add_trainer(e,'Référent Test','referent@example.fr',None,'admin');tr2=add_trainer(e,'Formateur Essai','form@example.fr',None,'admin')
    course,_,_=store_document(e,b'cours','Support.pdf','COURS','admin',action_id=a)
    pip,_,_=store_document(e,b'results','Analyse.pdf','PIP_RIASEC_ONET','connector',action_id=a,beneficiary_id=b1,participant_id=p1)
    qap,_,_=store_document(e,b'qap','Attentes.pdf','QAP','admin',action_id=a,beneficiary_id=b2,participant_id=p2,audience='BENEFICIARY_ONLY')
    assert list_trainer_documents(e,tr,a)==[]
    assign_action_trainer(e,a,tr,'admin',is_referent=True)
    assign_action_trainer(e,a,tr2,'admin')
    assert {d['id'] for d in list_trainer_documents(e,tr,a)}=={course,pip,qap}
    assert {d['id'] for d in list_trainer_documents(e,tr2,a)}=={course,qap}
    with pytest.raises(PermissionError):read_document_for_actor(e,pip,'TRAINER',tr2,action_id=a)
    assert read_document_for_actor(e,pip,'TRAINER',tr,action_id=a)==b'results'
    unassign_action_trainer(e,a,tr,'admin')
    assert list_trainer_documents(e,tr,a)==[]


def test_trainer_upload_requires_active_assignment_and_upload_permission(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e)
    tid=add_trainer(e,'Formateur','teacher@example.fr',None,'admin')
    with pytest.raises(PermissionError):store_document_for_actor(e,'TRAINER',tid,b'test','Cours.pdf',a)
    assign_action_trainer(e,a,tid,'admin')
    with pytest.raises(PermissionError):store_document_for_actor(e,'TRAINER',tid,b'test','Cours.pdf',a)
    execute(e,'UPDATE trainers SET can_upload_documents=1 WHERE id=:t',{'t':tid})
    ref,_,_=store_document_for_actor(e,'TRAINER',tid,b'cours','Cours.pdf',a)
    assert read_document_for_actor(e,ref,'TRAINER',tid,action_id=a)==b'cours'
    with pytest.raises(PermissionError):store_document_for_actor(e,'TRAINER',tid,b'qap','QAP.pdf',a,category='QAP')


def test_soft_archive_keeps_history_and_bytes(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);_,b1=make_person(e,a,'ONE')
    ref,digest,_=store_document(e,b'keep','Keep.pdf','COURS','admin',action_id=a)
    path=Path(one(e,'SELECT storage_path FROM stored_files WHERE sha256=:h',{'h':digest})['storage_path'])
    assert delete_document_reference(e,ref,'admin')
    assert path.read_bytes()==b'keep'
    assert not list_beneficiary_documents(e,b1)
    assert one(e,'SELECT deleted_at FROM document_references WHERE id=:r',{'r':ref})['deleted_at']
    assert not delete_document_reference(e,ref,'admin')


def test_personal_documents_excluded_from_client_participant_bundle(tmp_path,monkeypatch):
    import services,pdf_utils
    e=setup(tmp_path,monkeypatch);a=make_action(e);p1,b1=make_person(e,a,'ONE')
    store_document(e,b'private','Analyse_PIP.pdf','PIP_RIASEC_ONET','connector',action_id=a,beneficiary_id=b1,participant_id=p1)
    execute(e,"UPDATE actions SET status='CLOTUREE' WHERE id=:a",{'a':a})
    monkeypatch.setattr(services,'can_issue_certificate',lambda *args,**kwargs:(True,[]))
    monkeypatch.setattr(pdf_utils,'individual_pdf',lambda *args,**kwargs:b'presence')
    monkeypatch.setattr(pdf_utils,'certificate_pdf',lambda *args,**kwargs:b'certificat')
    with zipfile.ZipFile(io.BytesIO(participant_final_zip(e,p1))) as z:
        assert len(z.namelist())==2 and all('PIP' not in name for name in z.namelist())
    with zipfile.ZipFile(io.BytesIO(participant_final_zip(e,p1,'BENEFICIARY'))) as z:
        assert any('Analyse_PIP.pdf' in name for name in z.namelist())


def test_worker_blocks_old_cold_file_and_never_resends_old_final_zip(tmp_path,monkeypatch):
    import worker,services
    e=setup(tmp_path,monkeypatch);a=make_action(e)
    old=tmp_path/'old_unsafe.zip';old.write_bytes(b'ancienne archive confidentielle')
    execute(e,'UPDATE actions SET final_bundle_path=:p WHERE id=:a',{'p':str(old),'a':a})
    monkeypatch.setattr(services,'action_final_bundle',lambda *args,**kwargs:b'justificatifs autorises')
    subject,body,attachment=worker._client_transmission_content(e,{'action_id':a,'transmission_type':'FINAL'})
    assert attachment['data']==b'justificatifs autorises' and attachment['data']!=old.read_bytes()
    with pytest.raises(PermissionError):worker._client_transmission_content(e,{'action_id':a,'transmission_type':'COLD'})


def test_admin_metadata_not_content_for_private(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);p,b=make_person(e,a,'ONE')
    ref,_,_=store_document(e,b'prive','Confidentiel.pdf','BENEFICIAIRE','beneficiary',action_id=a,beneficiary_id=b,participant_id=p)
    assert any(d['id']==ref for d in list_admin_documents(e,'admin@test.fr',a))
    with pytest.raises(PermissionError):read_document_for_actor(e,ref,'ADMIN','admin@test.fr',action_id=a)
    assert list_admin_documents(e,'inconnu@example.fr',a)==[]


def test_integrity_hash_checked_before_delivery(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);_,b=make_person(e,a,'ONE')
    ref,h,_=store_document(e,b'original','Support.pdf','COURS','admin',action_id=a)
    path=Path(one(e,'SELECT storage_path FROM stored_files WHERE sha256=:h',{'h':h})['storage_path'])
    path.write_bytes(b'alteration')
    with pytest.raises(ValueError,match='Intégrité'):read_document_for_actor(e,ref,'BENEFICIARY',b)


def test_explicit_client_only_audience_never_leaks_to_beneficiary(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);p,b=make_person(e,a,'ONE')
    ref,_,_=store_document(e,b'private client note','Note_client.pdf','CLIENT_CONTRACTUEL','admin',
                          action_id=a,beneficiary_id=b,participant_id=p,audience='CLIENT_ONLY',visible_to_beneficiary=True)
    assert not any(x['id']==ref for x in list_beneficiary_documents(e,b))
    with pytest.raises(PermissionError):read_document_for_actor(e,ref,'BENEFICIARY',b)


def test_disabled_trainer_loses_document_rights_even_with_assignment(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e)
    tid=add_trainer(e,'Test Inactif','off@example.fr',None,'admin')
    assign_action_trainer(e,a,tid,'admin',is_referent=True)
    ref,_,_=store_document(e,b'course','Cours.pdf','COURS','admin',action_id=a)
    assert [x['id'] for x in list_trainer_documents(e,tid,a)]==[ref]
    execute(e,'UPDATE trainers SET active=0 WHERE id=:t',{'t':tid})
    assert list_trainer_documents(e,tid,a)==[]
    with pytest.raises(PermissionError):read_document_for_actor(e,ref,'TRAINER',tid,action_id=a)


def test_corrupted_file_refused_in_full_beneficiary_zip(tmp_path,monkeypatch):
    e=setup(tmp_path,monkeypatch);a=make_action(e);_,b=make_person(e,a,'ONE')
    _,h,_=store_document(e,b'untampered','Original.pdf','COURS','admin',action_id=a)
    path=Path(one(e,'SELECT storage_path FROM stored_files WHERE sha256=:h',{'h':h})['storage_path'])
    path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='Intégrité'):
        beneficiary_portal_zip(e,b)


def test_worker_quarantines_legacy_cold_transmission_without_sending(tmp_path,monkeypatch):
    import worker
    from services import queue_client_transmission
    e=setup(tmp_path,monkeypatch);a=make_action(e)
    queue_client_transmission(e,a,'COLD','raw-answers.pdf',['hr@example.fr'],'admin')
    sent=[]
    monkeypatch.setattr(worker,'send_mail',lambda *args,**kwargs:sent.append(args))
    assert worker._run_client_transmissions(e,{'enabled':True},10)==0
    assert sent==[]
    assert one(e,'SELECT status FROM client_transmissions WHERE action_id=:a',{'a':a})['status']=='BLOCKED_PRIVACY'
