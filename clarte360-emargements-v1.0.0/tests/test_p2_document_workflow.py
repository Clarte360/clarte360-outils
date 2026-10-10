"""P2: versions, publication, notifications et exports documentaires - sans donnees reelles."""
import io
import json
import zipfile
from pathlib import Path
import pytest

from db import make_engine, init_db, one, q, execute, utcnow_iso
from services import (
    create_action, add_participant, create_beneficiary_from_participant,
    create_beneficiary_portal_invitation, add_trainer, assign_action_trainer,
    unassign_action_trainer, store_document, store_document_for_actor,
    list_action_documents, list_beneficiary_documents, list_trainer_documents,
    read_document_for_actor, set_document_publication, set_document_validation,
    list_document_versions_admin, list_document_notifications,
    mark_document_notification_read, set_document_notification_preference,
    document_notification_preference, export_action_documents_zip,
    delete_document_reference,
)


def make_db(tmp_path, monkeypatch):
    import services
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'blobs')
    services.BENEFICIARY_DOC_DIR.mkdir(exist_ok=True)
    e=make_engine(f'sqlite:///{tmp_path / "p2.sqlite"}')
    init_db(e)
    execute(e,"INSERT INTO admins(email,password_hash,role,active,created_at) VALUES('admin@test.fr','dummy','ADMIN',1,:t)",
            {'t':utcnow_iso()})
    return e


def action(e, code='P2-1',nature='FORMATION'):
    return create_action(e,{'action_no':code,'title':'Essai P2','subtitle':None,
        'nature':nature,'mode':'INTRA','client_name':'Client X','client_type':'ENTREPRISE',
        'group_code':None,'planned_hours':7,'expected_participants':2,
        'admin_email':'admin@test.fr','trainer_name':None,'trainer_email':None,
        'location':'Paris','notes':None,'source':'TEST'},'admin@test.fr')


def person(e, aid, surname='ONE'):
    pid,_=add_participant(e,aid,{'last_name':surname,'first_name':'Marie','birth_date':'1991-03-01',
        'email':surname.lower()+'@example.fr','company_name':'Client X','phone':None},'admin@test.fr')
    bid=create_beneficiary_from_participant(e,pid,'admin@test.fr')
    create_beneficiary_portal_invitation(e,bid,surname.lower()+'@example.fr','admin@test.fr')
    return pid,bid


def notice_ids(e,role,id,aid=None):
    return [x['id'] for x in list_document_notifications(e,role,id,action_id=aid)]


def test_exact_same_course_deposit_reuses_logical_reference(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e)
    r1,h,_=store_document(e,b'identique','Cours.pdf','COURS',action_id=a)
    r2,h2,dedup=store_document(e,b'identique','Cours.pdf','COURS',action_id=a)
    assert r1==r2 and h==h2 and dedup
    assert len(list_action_documents(e,a))==1
    assert one(e,'SELECT count(*) n FROM document_references')['n']==1


def test_same_content_same_scope_with_second_label_is_not_duplicate_ref(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e)
    r1,_,_=store_document(e,b'same bytes','Cours.pdf','COURS',action_id=a)
    r2,_,_=store_document(e,b'same bytes','Autre_label.pdf','COURS',action_id=a)
    assert r1==r2
    assert len(list_action_documents(e,a))==1


def test_replaced_file_is_new_version_with_original_preserved(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    r1,old,_=store_document(e,b'v1','Cours.pdf','COURS',action_id=a)
    r2,new,_=store_document(e,b'v2','Cours.pdf','COURS',action_id=a)
    assert r2!=r1 and new!=old
    refs=list_action_documents(e,a)
    assert len(refs)==1 and refs[0]['id']==r2 and refs[0]['version_no']==2
    versions=list_document_versions_admin(e,r2,'admin@test.fr')
    assert {v['id'] for v in versions}=={r1,r2}
    assert one(e,'SELECT superseded_at FROM document_references WHERE id=:i',{'i':r1})['superseded_at']
    assert read_document_for_actor(e,r2,'BENEFICIARY',b)==b'v2'
    with pytest.raises(PermissionError):read_document_for_actor(e,r1,'BENEFICIARY',b)
    assert Path(one(e,'SELECT storage_path FROM stored_files WHERE sha256=:h',{'h':old})['storage_path']).read_bytes()==b'v1'


def test_only_identical_name_different_action_preserves_separation(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a1=action(e);a2=action(e,'P2-2')
    r1,_,_=store_document(e,b'same','Cours.pdf','COURS',action_id=a1)
    r2,_,_=store_document(e,b'same','Cours.pdf','COURS',action_id=a2)
    assert r1!=r2


def test_finalized_version_requires_reason_to_open_new_version(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e)
    r,_,_=store_document(e,b'v1','Cours.pdf','COURS',action_id=a)
    assert set_document_validation(e,r,'FINALISE','admin@test.fr')
    with pytest.raises(ValueError,match='motif explicite'):
        store_document(e,b'v2','Cours.pdf','COURS',action_id=a)
    assert len(list_action_documents(e,a))==1
    new,_,_=store_document(e,b'v2','Cours.pdf','COURS',action_id=a,revision_reason='Correction validée')
    assert new!=r and one(e,'SELECT revision_reason FROM document_references WHERE id=:i',{'i':new})['revision_reason']=='Correction validée'
    with pytest.raises(ValueError,match='introuvable|verrouillé'):
        set_document_validation(e,r,'A_VERIFIER','admin@test.fr')


def test_draft_saved_invisible_until_explicit_publication(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    r,_,_=store_document_for_actor(e,'ADMIN','admin@test.fr',b'hello','Cours.pdf',a,publish=False)
    assert not list_beneficiary_documents(e,b)
    assert not list_document_notifications(e,'BENEFICIARY',b)
    assert one(e,'SELECT publication_status FROM document_references WHERE id=:i',{'i':r})['publication_status']=='BROUILLON'
    assert set_document_publication(e,r,True,'admin@test.fr')
    assert {d['id'] for d in list_beneficiary_documents(e,b)}=={r}
    assert len(notice_ids(e,'BENEFICIARY',b))==1
    assert not set_document_publication(e,r,True,'admin@test.fr')
    assert len(notice_ids(e,'BENEFICIARY',b))==1


def test_draft_unpublished_removes_access_and_hides_notification(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    r,_,_=store_document(e,b'doc','Cours.pdf','COURS',action_id=a)
    nid=notice_ids(e,'BENEFICIARY',b)[0]
    assert set_document_publication(e,r,False,'admin@test.fr')
    assert not list_beneficiary_documents(e,b)
    assert not list_document_notifications(e,'BENEFICIARY',b)
    with pytest.raises(PermissionError):mark_document_notification_read(e,nid,'BENEFICIARY',b)


def test_validation_is_independent_of_publication_and_admin_active_only(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    r,_,_=store_document(e,b'x','Cours.pdf','COURS',action_id=a,publish=False)
    assert set_document_validation(e,r,'VALIDE','admin@test.fr')
    assert not list_beneficiary_documents(e,b)
    assert one(e,'SELECT validation_status FROM document_references WHERE id=:i',{'i':r})['validation_status']=='VALIDE'
    with pytest.raises(PermissionError):set_document_publication(e,r,True,'inconnu@none.fr')
    with pytest.raises(PermissionError):set_document_validation(e,r,'FINALISE','inconnu@none.fr')


def test_notifications_are_scoped_per_action_and_not_client(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);a2=action(e,'P2-2')
    _,b1=person(e,a,'ONE');_,b2=person(e,a,'TWO');_,b3=person(e,a2,'THREE')
    r,_,_=store_document(e,b'cours','Support.pdf','COURS',action_id=a)
    assert len(notice_ids(e,'BENEFICIARY',b1))==1 and len(notice_ids(e,'BENEFICIARY',b2))==1
    assert not notice_ids(e,'BENEFICIARY',b3)
    assert not list_document_notifications(e,'CLIENT','drh@example.fr')
    with pytest.raises(PermissionError):mark_document_notification_read(e,notice_ids(e,'BENEFICIARY',b1)[0],'BENEFICIARY',b2)


def test_notice_read_timestamp_not_changed_by_repeated_read(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    store_document(e,b'cours','Cours.pdf','COURS',action_id=a)
    nid=notice_ids(e,'BENEFICIARY',b)[0]
    assert mark_document_notification_read(e,nid,'BENEFICIARY',b)
    first=one(e,'SELECT read_at FROM document_notifications WHERE id=:i',{'i':nid})['read_at']
    assert not mark_document_notification_read(e,nid,'BENEFICIARY',b)
    assert one(e,'SELECT read_at FROM document_notifications WHERE id=:i',{'i':nid})['read_at']==first


def test_assigned_trainer_receives_course_notice_but_unassigned_cannot_read(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e)
    tid=add_trainer(e,'F','trainer@example.fr',None,'admin');assign_action_trainer(e,a,tid,'admin')
    store_document(e,b'cours','Cours.pdf','COURS','admin',action_id=a)
    ns=notice_ids(e,'TRAINER',tid,a)
    assert len(ns)==1
    unassign_action_trainer(e,a,tid,'admin')
    assert not notice_ids(e,'TRAINER',tid,a)
    with pytest.raises(PermissionError):mark_document_notification_read(e,ns[0],'TRAINER',tid,a)


def test_private_qap_only_beneficiary_and_assigned_trainer(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);p1,b1=person(e,a,'ONE');_,b2=person(e,a,'TWO')
    t=add_trainer(e,'T','trainer@example.fr',None,'admin');assign_action_trainer(e,a,t,'admin')
    r,_,_=store_document(e,b'private','QAP.pdf','QAP','admin',action_id=a,beneficiary_id=b1,participant_id=p1,audience='BENEFICIARY_ONLY')
    assert len(notice_ids(e,'BENEFICIARY',b1))==1
    assert not notice_ids(e,'BENEFICIARY',b2)
    assert len(notice_ids(e,'TRAINER',t,a))==1
    with pytest.raises(PermissionError):read_document_for_actor(e,r,'BENEFICIARY',b2)


def test_zip_by_action_beneficiary_protects_peer_and_company(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);p1,b1=person(e,a,'ONE');p2,b2=person(e,a,'TWO')
    store_document(e,b'common','Cours.pdf','COURS','admin',action_id=a)
    store_document(e,b'private-one','Analyse.pdf','PIP_RIASEC_ONET','connector',action_id=a,beneficiary_id=b1,participant_id=p1)
    store_document(e,b'private-two','Analyse.pdf','PIP_RIASEC_ONET','connector',action_id=a,beneficiary_id=b2,participant_id=p2)
    store_document(e,b'client-secret','Facture.pdf','CLIENT_CONTRACTUEL','admin',action_id=a,audience='ADMIN_ONLY')
    with zipfile.ZipFile(io.BytesIO(export_action_documents_zip(e,a,'BENEFICIARY',b1))) as z:
        assert set(z.namelist())=={'manifest.json',*(x for x in z.namelist() if x.startswith('documents/'))}
        payload=b'\n'.join(z.read(n) for n in z.namelist() if n.startswith('documents/'))
        assert b'common' in payload and b'private-one' in payload
        assert b'private-two' not in payload and b'client-secret' not in payload
        doc=json.loads(z.read('manifest.json'))
        assert len(doc['documents'])==2
    with pytest.raises(PermissionError):export_action_documents_zip(e,a,'CLIENT','somebody')


def test_admin_zip_cannot_bypass_individual_confidentiality(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);p,b=person(e,a)
    store_document(e,b'private','Rapport.pdf','PIP_RIASEC_ONET','connector',action_id=a,beneficiary_id=b,participant_id=p)
    store_document(e,b'internal','Contrat.pdf','CLIENT_CONTRACTUEL','admin',action_id=a,audience='ADMIN_ONLY')
    with zipfile.ZipFile(io.BytesIO(export_action_documents_zip(e,a,'ADMIN','admin@test.fr'))) as z:
        payload=b'\n'.join(z.read(n) for n in z.namelist() if n.startswith('documents/'))
        assert b'private' not in payload and b'internal' in payload
    with pytest.raises(PermissionError):export_action_documents_zip(e,a,'ADMIN','attacker@test.fr')


def test_zip_fails_if_file_modified_after_hash(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    r,h,_=store_document(e,b'unchanged','Cours.pdf','COURS',action_id=a)
    path=Path(one(e,'SELECT storage_path FROM stored_files WHERE sha256=:h',{'h':h})['storage_path'])
    path.write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='Intégrité'):
        export_action_documents_zip(e,a,'BENEFICIARY',b)
    with pytest.raises(ValueError,match='intégrité'):
        store_document(e,b'unchanged','Cours.pdf','COURS',action_id=a)


def test_archive_keeps_original_and_refuses_access(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    r,h,_=store_document(e,b'original','Cours.pdf','COURS',action_id=a)
    assert delete_document_reference(e,r,'admin@test.fr')
    assert not list_beneficiary_documents(e,b)
    assert not list_document_notifications(e,'BENEFICIARY',b)
    assert one(e,'SELECT count(*) n FROM stored_files')['n']==1


def test_progress_callback_real_stages_monotonic_and_finish(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);calls=[]
    store_document(e,b'doc','Cours.pdf','COURS',action_id=a,
                   progress_callback=lambda label,ratio:calls.append((label,ratio)))
    assert calls and calls[-1][1]==1 and calls[0][1]>0
    assert all(calls[i][1]<=calls[i+1][1] for i in range(len(calls)-1))


def test_source_origin_and_retention_class_are_explicit(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e)
    execute(e,"UPDATE actions SET prestation_type='BILAN_DE_COMPETENCES' WHERE id=:a",{'a':a})
    r,_,_=store_document(e,b'report','Resultat.pdf','PIP_RIASEC_ONET','pip_connector',action_id=a,beneficiary_id=None,audience='ADMIN_ONLY')
    row=one(e,'SELECT source_kind,retention_class FROM document_references WHERE id=:i',{'i':r})
    assert row['source_kind']=='APPLICATION' and row['retention_class']=='BILAN_COMPETENCES_A_DEFINIR'


def test_filename_path_cannot_escape_archive_or_blob_folder(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e)
    r,_,_=store_document(e,b'text','../../unsafe.pdf','COURS',action_id=a)
    assert one(e,'SELECT display_name FROM document_references WHERE id=:i',{'i':r})['display_name']=='unsafe.pdf'
    r2,_,_=store_document(e,b'other','C:\\temp\\other.pdf','COURS',action_id=a)
    assert one(e,'SELECT display_name FROM document_references WHERE id=:i',{'i':r2})['display_name']=='other.pdf'


def test_email_pref_optin_and_worker_is_disabled_by_default(tmp_path,monkeypatch):
    from worker import _run_document_notifications
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    assert not document_notification_preference(e,'BENEFICIARY',b)
    assert set_document_notification_preference(e,'BENEFICIARY',b,True)
    store_document(e,b'secret','Secret.pdf','COURS',action_id=a)
    nid=notice_ids(e,'BENEFICIARY',b)[0]
    assert one(e,'SELECT email_status FROM document_notifications WHERE id=:i',{'i':nid})['email_status']=='A_ENVOYER'
    calls=[]
    monkeypatch.setattr('worker.send_mail',lambda cfg,to,subject,body:calls.append((to,subject,body)))
    assert _run_document_notifications(e,{}, {},'https://example.org')==0 and not calls
    assert _run_document_notifications(e,{}, {'documents':{'email_notifications_enabled':True}},'https://example.org')==1
    assert len(calls)==1 and 'Secret.pdf' not in str(calls)
    assert 'Nouveau document' in calls[0][1] and 'Secret' not in calls[0][2]
    assert _run_document_notifications(e,{}, {'documents':{'email_notifications_enabled':True}},'https://example.org')==0


def test_optout_prevents_pending_email(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    set_document_notification_preference(e,'BENEFICIARY',b,True)
    store_document(e,b'info','Cours.pdf','COURS',action_id=a)
    set_document_notification_preference(e,'BENEFICIARY',b,False)
    assert one(e,'SELECT email_status FROM document_notifications')['email_status']=='NON_DEMANDE'
    assert not document_notification_preference(e,'BENEFICIARY',b)


def test_worker_rechecks_scope_and_cancels_pending_mail(tmp_path,monkeypatch):
    from worker import _run_document_notifications
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    set_document_notification_preference(e,'BENEFICIARY',b,True)
    r,_,_=store_document(e,b'doc','Cours.pdf','COURS',action_id=a)
    set_document_publication(e,r,False,'admin@test.fr')
    calls=[]
    monkeypatch.setattr('worker.send_mail',lambda *args:calls.append(args))
    assert _run_document_notifications(e,{}, {'documents':{'email_notifications_enabled':True}},'https://example.org')==0
    assert not calls
    assert one(e,'SELECT email_status FROM document_notifications')['email_status']=='ANNULE'


def test_schema_is_additive_and_default_legacy_docs_published(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    r,_,_=store_document(e,b'first','Cours.pdf','COURS',action_id=a)
    # Re-initialization on an existing DB must be idempotent and preserve all references.
    init_db(e)
    assert read_document_for_actor(e,r,'BENEFICIARY',b)==b'first'
    assert one(e,'SELECT count(*) n FROM document_references')['n']==1


def test_trainer_zip_does_not_expose_other_private_results(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);p,b=person(e,a)
    t1=add_trainer(e,'Référent','referent@example.fr',None,'admin')
    t2=add_trainer(e,'Intervenant','inter@example.fr',None,'admin')
    assign_action_trainer(e,a,t1,'admin',is_referent=True);assign_action_trainer(e,a,t2,'admin')
    store_document(e,b'public','Cours.pdf','COURS',action_id=a)
    store_document(e,b'private','Rapport.pdf','PIP_RIASEC_ONET','connector',action_id=a,beneficiary_id=b,participant_id=p)
    with zipfile.ZipFile(io.BytesIO(export_action_documents_zip(e,a,'TRAINER',t2))) as z:
        payload=b'\n'.join(z.read(n) for n in z.namelist() if n.startswith('documents/'))
        assert b'public' in payload and b'private' not in payload


def test_new_draft_never_hides_last_published_version(tmp_path,monkeypatch):
    e=make_db(tmp_path,monkeypatch);a=action(e);_,b=person(e,a)
    old,_,_=store_document(e,b'public1','Cours.pdf','COURS',action_id=a)
    draft,_,_=store_document(e,b'draft2','Cours.pdf','COURS',action_id=a,publish=False)
    assert old!=draft
    assert read_document_for_actor(e,old,'BENEFICIARY',b)==b'public1'
    with pytest.raises(PermissionError):read_document_for_actor(e,draft,'BENEFICIARY',b)
    assert {row['id'] for row in list_beneficiary_documents(e,b)}=={old}
    set_document_publication(e,draft,True,'admin@test.fr')
    assert {row['id'] for row in list_beneficiary_documents(e,b)}=={draft}
    assert one(e,'SELECT publication_status FROM document_references WHERE id=:i',{'i':old})['publication_status']=='REMPLACE'
    assert read_document_for_actor(e,draft,'BENEFICIARY',b)==b'draft2'
    set_document_publication(e,draft,False,'admin@test.fr')
    assert not list_beneficiary_documents(e,b)  # pas de remise en ligne silencieuse de l'ancienne version
