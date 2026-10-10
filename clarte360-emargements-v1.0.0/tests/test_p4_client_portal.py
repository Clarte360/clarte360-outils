"""P4 - ACL contextuelles Client/DRH et non-régression des droits sensibles."""
import ast
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from db import make_engine, init_db, execute, one, q, utcnow_iso
from services import (create_action, create_crm_contact, link_crm_contact_action,
                      store_document, list_beneficiary_documents, read_document_for_actor,
                      set_document_publication, set_document_validation,
                      delete_document_reference, export_action_documents_zip)
from persistent_session import create_session, resolve_session
from client_portal import (
    create_client_portal_account, list_client_accounts_admin, set_client_account_active,
    issue_client_access_token, redeem_client_access_token, verify_client_login,
    client_portal_identity, grant_client_action, revoke_client_action, client_action_permission,
    list_client_actions, client_action_summary, client_public_schedule,
    create_client_delivery, share_client_document, revoke_client_document,
    list_client_documents, read_client_document, export_client_action_zip,
    client_upload_document, list_client_submissions, client_go14_contract_snapshot,
    MIN_AGGREGATE,
)

ADMIN='admin@clarte360.fr'
GOOD_PASSWORD='TresBonMotDePasse_2026!'

@pytest.fixture
def env(tmp_path,monkeypatch):
    import services
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'blobs')
    (tmp_path/'blobs').mkdir()
    e=make_engine(f'sqlite:///{tmp_path / "p4_test.db"}')
    init_db(e)
    execute(e,'INSERT INTO admins(email,password_hash,active,role,created_at) VALUES(:e,:p,1,\'ADMIN\',:t)',
            {'e':ADMIN,'p':'placeholder','t':utcnow_iso()})
    return e


def action(e,name,nature='FORMATION'):
    return create_action(e,{'action_no':name,'title':'Formation collective '+name,'subtitle':None,
       'nature':nature,'mode':'INTRA','client_name':'Entreprise X','client_type':'Professionnel',
       'group_code':None,'planned_hours':7,'expected_participants':10,'admin_email':ADMIN,
       'trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'},ADMIN)


def contact(e,stem):
    return create_crm_contact(e,''.join(ch for ch in stem.capitalize() if ch.isalpha()),'Client',f'{stem}@example.com',company='Entreprise X')['id']


def activate(e,account):
    token=issue_client_access_token(e,account,ADMIN)
    assert len(token)>=32
    assert redeem_client_access_token(e,token,GOOD_PASSWORD)==account
    return token


def client(e,stem='alice',active=True):
    c=contact(e,stem)
    acc=create_client_portal_account(e,c,ADMIN)
    if active:activate(e,acc)
    return acc


def test_new_schema_is_additive_and_init_is_idempotent(env):
    init_db(env)
    for t in ('client_portal_accounts','client_portal_tokens','client_action_grants','client_document_shares'):
        assert one(env,"SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n",{'n':t})
    assert one(env,"SELECT COUNT(*) n FROM actions")['n']==0
    assert one(env,"SELECT COUNT(*) n FROM crm_contacts")['n']==0


def test_crm_link_does_not_grant_portal_rights(env):
    aid=action(env,'P4-001');cc=contact(env,'associe')
    link_crm_contact_action(env,cc,aid,'CLIENT',ADMIN)
    account=create_client_portal_account(env,cc,ADMIN)
    activate(env,account)
    assert list_client_actions(env,account)==[]
    with pytest.raises(PermissionError):client_action_summary(env,account,aid)


def test_client_role_scope_is_explicit_per_action(env):
    a1=action(env,'P4-101');a2=action(env,'P4-102')
    cl=client(env)
    grant_client_action(env,cl,a1,ADMIN,'PRESCRIPTEUR')
    assert [r['id'] for r in list_client_actions(env,cl)]==[a1]
    with pytest.raises(PermissionError):client_action_summary(env,cl,a2)
    assert client_action_summary(env,cl,a1)['role']=='PRESCRIPTEUR'


def test_client_admin_can_only_see_explicit_grants(env):
    a1=action(env,'P4-201');a2=action(env,'P4-202')
    cl=client(env)
    grant_client_action(env,cl,a1,ADMIN,'CLIENT_ADMIN',can_download=True)
    assert list_client_actions(env,cl)[0]['role']=='CLIENT_ADMIN'
    with pytest.raises(PermissionError):client_action_permission(env,cl,a2)


@pytest.mark.parametrize('role',['CLIENT_ADMIN','PRESCRIPTEUR','ROOT','ADMIN',''])
def test_only_client_roles_allowed(env,role):
    aid=action(env,f'ROLE-{role or "EMPTY"}')
    cl=client(env,'person'+str(len(role)))
    if role in ('CLIENT_ADMIN','PRESCRIPTEUR'):
        grant_client_action(env,cl,aid,ADMIN,role)
    else:
        with pytest.raises(ValueError):grant_client_action(env,cl,aid,ADMIN,role)


def test_client_without_download_cannot_list_or_read(env):
    aid=action(env,'P4-301');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,'PRESCRIPTEUR')
    with pytest.raises(PermissionError):list_client_documents(env,cl,aid)
    with pytest.raises(PermissionError):export_client_action_zip(env,cl,aid)


def test_crm_master_remains_unique(env):
    c=contact(env,'uniq')
    first=create_client_portal_account(env,c,ADMIN)
    second=create_client_portal_account(env,c,ADMIN)
    assert first==second
    assert one(env,'SELECT COUNT(*) n FROM crm_contacts')['n']==1
    assert one(env,'SELECT COUNT(*) n FROM client_portal_accounts')['n']==1


def test_duplicate_contact_email_is_not_second_identity(env):
    c=contact(env,'same')
    create_client_portal_account(env,c,ADMIN)
    c2=create_crm_contact(env,'Other','Client','same@example.com')['id']
    with pytest.raises(ValueError,match='déjà'):create_client_portal_account(env,c2,ADMIN)


def test_crm_email_change_blocks_login_and_read(env):
    aid=action(env,'P4-401');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN)
    assert verify_client_login(env,'alice@example.com',GOOD_PASSWORD)
    execute(env,"UPDATE crm_contacts SET email='new@example.com' WHERE email='alice@example.com'")
    assert verify_client_login(env,'alice@example.com',GOOD_PASSWORD) is None
    with pytest.raises(PermissionError):list_client_actions(env,cl)


def test_no_admin_rights_without_active_admin(env):
    cc=contact(env,'bob')
    with pytest.raises(PermissionError):create_client_portal_account(env,cc,'unknown@none.com')
    with pytest.raises(PermissionError):list_client_accounts_admin(env,'unknown@none.com')
    c=create_client_portal_account(env,cc,ADMIN)
    with pytest.raises(PermissionError):grant_client_action(env,c,action(env,'P4-501'),'unknown@none.com')


def test_token_hash_single_use_and_wrong_token_rejected(env):
    cl=client(env,'nouveau',active=False)
    token=issue_client_access_token(env,cl,ADMIN)
    row=one(env,'SELECT token_hash,used_at FROM client_portal_tokens WHERE account_id=:i',{'i':cl})
    assert row['token_hash']==hashlib.sha256(token.encode()).hexdigest()
    assert token not in row['token_hash']
    with pytest.raises(ValueError):redeem_client_access_token(env,'bogus-token',GOOD_PASSWORD)
    with pytest.raises(ValueError):redeem_client_access_token(env,token,'short')
    assert redeem_client_access_token(env,token,GOOD_PASSWORD)==cl
    with pytest.raises(ValueError):redeem_client_access_token(env,token,GOOD_PASSWORD)
    assert verify_client_login(env,'nouveau@example.com',GOOD_PASSWORD)


def test_expired_client_token_rejected(env):
    cl=client(env,'expired',active=False)
    token=issue_client_access_token(env,cl,ADMIN)
    execute(env,"UPDATE client_portal_tokens SET expires_at='2020-01-01T00:00:00+00:00'")
    with pytest.raises(ValueError):redeem_client_access_token(env,token,GOOD_PASSWORD)


def test_token_issuance_revokes_existing_persistent_sessions(env):
    cl=client(env,'renewal');session=create_session(env,'CLIENT',cl)
    assert resolve_session(env,session,expected_type='CLIENT')
    issue_client_access_token(env,cl,ADMIN,kind='RESET')
    assert resolve_session(env,session,expected_type='CLIENT') is None
    assert verify_client_login(env,'renewal@example.com',GOOD_PASSWORD) is None


def test_reset_updates_password_and_expires_prior_links(env):
    cl=client(env,'reset')
    first=issue_client_access_token(env,cl,ADMIN,'RESET')
    second=issue_client_access_token(env,cl,ADMIN,'RESET')
    with pytest.raises(ValueError):redeem_client_access_token(env,first,'DifferentPassword_2026')
    assert redeem_client_access_token(env,second,'DifferentPassword_2026')==cl
    assert verify_client_login(env,'reset@example.com',GOOD_PASSWORD) is None
    assert verify_client_login(env,'reset@example.com','DifferentPassword_2026')


def test_deactivation_revokes_access_and_sessions_even_after_reactivation(env):
    aid=action(env,'P4-601');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,'CLIENT_ADMIN',can_download=True)
    session=create_session(env,'CLIENT',cl)
    set_client_account_active(env,cl,False,ADMIN)
    assert resolve_session(env,session,expected_type='CLIENT') is None
    with pytest.raises(PermissionError):list_client_actions(env,cl)
    set_client_account_active(env,cl,True,ADMIN)
    assert list_client_actions(env,cl)==[]


def test_revoking_action_does_not_revive_document_shares_on_regrant(env):
    aid=action(env,'P4-701');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,can_download=True)
    doc,_,_=create_client_delivery(env,aid,b'doc','proof.pdf',ADMIN)
    set_document_validation(env,doc,'FINALISE',ADMIN)
    set_document_publication(env,doc,True,ADMIN)
    share_client_document(env,doc,cl,ADMIN)
    assert len(list_client_documents(env,cl,aid))==1
    revoke_client_action(env,cl,aid,ADMIN)
    with pytest.raises(PermissionError):list_client_documents(env,cl,aid)
    grant_client_action(env,cl,aid,ADMIN,can_download=True)
    assert list_client_documents(env,cl,aid)==[]


def test_only_shared_approved_documents_can_be_downloaded(env):
    aid=action(env,'P4-801');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,can_download=True)
    rid,_,_=create_client_delivery(env,aid,b'confirme','justif.pdf',ADMIN)
    assert not list_client_documents(env,cl,aid)
    with pytest.raises(PermissionError):share_client_document(env,rid,cl,ADMIN)
    set_document_validation(env,rid,'VALIDE',ADMIN)
    with pytest.raises(PermissionError):share_client_document(env,rid,cl,ADMIN)
    set_document_publication(env,rid,True,ADMIN)
    assert not list_client_documents(env,cl,aid)
    share_client_document(env,rid,cl,ADMIN)
    assert read_client_document(env,rid,cl,aid)==b'confirme'
    assert read_document_for_actor(env,rid,'CLIENT',cl,action_id=aid)==b'confirme'


def test_two_clients_same_action_do_not_receive_each_others_documents(env):
    aid=action(env,'P4-901');a=client(env,'alpha');b=client(env,'beta')
    for cl in (a,b):grant_client_action(env,cl,aid,ADMIN,can_download=True)
    ref,_,_=create_client_delivery(env,aid,b'reserved','archive.pdf',ADMIN)
    set_document_validation(env,ref,'VALIDE',ADMIN)
    set_document_publication(env,ref,True,ADMIN)
    share_client_document(env,ref,a,ADMIN)
    assert {d['id'] for d in list_client_documents(env,a,aid)}=={ref}
    assert list_client_documents(env,b,aid)==[]
    with pytest.raises(PermissionError):read_document_for_actor(env,ref,'CLIENT',b,action_id=aid)


def test_archive_and_revoke_hide_client_document(env):
    aid=action(env,'P4-1001');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,can_download=True)
    rid,_,_=create_client_delivery(env,aid,b'content','archive.pdf',ADMIN)
    set_document_validation(env,rid,'VALIDE',ADMIN);set_document_publication(env,rid,True,ADMIN)
    share_client_document(env,rid,cl,ADMIN)
    revoke_client_document(env,rid,cl,ADMIN)
    assert list_client_documents(env,cl,aid)==[]
    share_client_document(env,rid,cl,ADMIN)
    delete_document_reference(env,rid,ADMIN)
    assert list_client_documents(env,cl,aid)==[]


def test_client_document_never_visible_to_beneficiary(env):
    aid=action(env,'P4-1101');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,can_download=True)
    ref,_,_=create_client_delivery(env,aid,b'client-only','proof.pdf',ADMIN)
    set_document_validation(env,ref,'VALIDE',ADMIN);set_document_publication(env,ref,True,ADMIN)
    share_client_document(env,ref,cl,ADMIN)
    assert one(env,'SELECT audience,visible_to_beneficiary,beneficiary_id,participant_id FROM document_references WHERE id=:i',{'i':ref})['audience']=='CLIENT_ONLY'
    with pytest.raises(PermissionError):read_document_for_actor(env,ref,'BENEFICIARY',999,action_id=aid)
    assert read_document_for_actor(env,ref,'ADMIN',ADMIN,action_id=aid)==b'client-only'


def test_old_client_contract_and_course_are_not_shared(env):
    aid=action(env,'P4-1201');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,can_download=True)
    for category in ('COURS','CONTRAT_CLIENT','PIP_RIASEC_ONET','IPIP_NEO120'):
        rid,_,_=store_document(env,b'PRIVATE',category+'.pdf',category,action_id=aid,audience='CLIENT_ONLY')
        set_document_validation(env,rid,'VALIDE',ADMIN)
        with pytest.raises(PermissionError):share_client_document(env,rid,cl,ADMIN)
    assert list_client_documents(env,cl,aid)==[]


def test_cross_action_reference_is_rejected(env):
    a1=action(env,'P4-1301');a2=action(env,'P4-1302');cl=client(env)
    grant_client_action(env,cl,a1,ADMIN,can_download=True)
    grant_client_action(env,cl,a2,ADMIN,can_download=True)
    ref,_,_=create_client_delivery(env,a1,b'data','proof.pdf',ADMIN)
    set_document_validation(env,ref,'VALIDE',ADMIN);set_document_publication(env,ref,True,ADMIN)
    share_client_document(env,ref,cl,ADMIN)
    with pytest.raises(PermissionError):read_client_document(env,ref,cl,a2)
    assert read_client_document(env,ref,cl,a1)==b'data'


def test_wrong_account_cannot_upload(env):
    aid=action(env,'P4-1401');a=client(env,'alpha');b=client(env,'beta')
    grant_client_action(env,a,aid,ADMIN,can_upload=True)
    with pytest.raises(PermissionError):client_upload_document(env,b,aid,b'content','note.pdf')
    assert not list_client_submissions(env,a,aid)


def test_client_upload_never_published_without_admin(env):
    aid=action(env,'P4-1501');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,can_upload=True)
    ref,_,_=client_upload_document(env,cl,aid,b'uploaded','client.pdf')
    d=one(env,'SELECT * FROM document_references WHERE id=:i',{'i':ref})
    assert d['publication_status']=='BROUILLON'
    assert d['visible_to_beneficiary']==0
    assert d['uploaded_by']==f'client_portal:{cl}'
    assert list_client_submissions(env,cl,aid)[0]['id']==ref
    with pytest.raises(PermissionError):read_client_document(env,ref,cl,aid)


def test_two_clients_same_file_label_never_collide(env):
    aid=action(env,'P4-1601');a=client(env,'alpha');b=client(env,'beta')
    for cl in (a,b):grant_client_action(env,cl,aid,ADMIN,can_upload=True)
    r1,_,_=client_upload_document(env,a,aid,b'first','identique.pdf')
    r2,_,_=client_upload_document(env,b,aid,b'second','identique.pdf')
    assert r1!=r2
    assert [r['id'] for r in list_client_submissions(env,a,aid)]==[r1]
    assert [r['id'] for r in list_client_submissions(env,b,aid)]==[r2]
    assert one(env,'SELECT logical_key FROM document_references WHERE id=:i',{'i':r1}) != one(env,'SELECT logical_key FROM document_references WHERE id=:i',{'i':r2})


def test_identical_file_two_clients_has_distinct_references(env):
    aid=action(env,'P4-1701');a=client(env,'alpha');b=client(env,'beta')
    for cl in (a,b):grant_client_action(env,cl,aid,ADMIN,can_upload=True)
    r1,_,_=client_upload_document(env,a,aid,b'same','identique.pdf')
    r2,_,_=client_upload_document(env,b,aid,b'same','identique.pdf')
    assert r1!=r2


def test_same_client_idempotent_upload(env):
    aid=action(env,'P4-1801');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,can_upload=True)
    r1,_,_=client_upload_document(env,cl,aid,b'same','identique.pdf')
    r2,_,dedup=client_upload_document(env,cl,aid,b'same','identique.pdf')
    assert r1==r2 and dedup


@pytest.mark.parametrize('nature', ['BILAN DE COMPETENCES','COACHING','ACCOMPAGNEMENT INDIVIDUEL'])
def test_bilan_and_coaching_document_delivery_denied(env,nature):
    aid=action(env,'BC-'+nature[:6],nature)
    cl=client(env)
    with pytest.raises(PermissionError):grant_client_action(env,cl,aid,ADMIN,can_upload=True,can_download=True)
    grant_client_action(env,cl,aid,ADMIN,can_upload=False,can_download=False)
    with pytest.raises(PermissionError):create_client_delivery(env,aid,b'personnel','resultat.pdf',ADMIN)
    with pytest.raises(PermissionError):client_upload_document(env,cl,aid,b'personnel','analyse.pdf')
    assert not client_action_summary(env,cl,aid)['collective_training']


def test_client_zip_only_authorized_manifest(env):
    aid=action(env,'P4-1901');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,can_download=True)
    r,_,_=create_client_delivery(env,aid,b'official','preuve.pdf',ADMIN)
    set_document_validation(env,r,'FINALISE',ADMIN);set_document_publication(env,r,True,ADMIN)
    share_client_document(env,r,cl,ADMIN)
    buf=export_client_action_zip(env,cl,aid)
    with zipfile.ZipFile(io.BytesIO(buf)) as z:
        names=z.namelist()
        assert len(names)==2 and 'manifest.json' in names
        info=json.loads(z.read('manifest.json'))
        assert info['action_id']==aid
        assert len(info['documents'])==1
        assert info['documents'][0]['sha256']==hashlib.sha256(b'official').hexdigest()
        assert z.read(info['documents'][0]['file'])==b'official'
    # Le ZIP documentaire générique réutilise exactement les mêmes ACL CLIENT.
    with zipfile.ZipFile(io.BytesIO(export_action_documents_zip(env,aid,'CLIENT',cl))) as z:
        info=json.loads(z.read('manifest.json'))
        assert len(info['documents'])==1


def test_source_file_integrity_blocks_modified_bytes(env):
    aid=action(env,'P4-2001');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,can_download=True)
    r,_,_=create_client_delivery(env,aid,b'trusted','proof.pdf',ADMIN)
    set_document_validation(env,r,'VALIDE',ADMIN);set_document_publication(env,r,True,ADMIN)
    share_client_document(env,r,cl,ADMIN)
    path=Path(one(env,'SELECT sf.storage_path FROM document_references dr JOIN stored_files sf ON sf.id=dr.stored_file_id WHERE dr.id=:r',{'r':r})['storage_path'])
    path.write_bytes(b'altered')
    with pytest.raises(ValueError):read_client_document(env,r,cl,aid)


def test_client_summary_counts_only_collective_five_or_more(env):
    aid=action(env,'P4-2101');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN)
    summary=client_action_summary(env,cl,aid)
    assert 'participants_count' not in summary and not summary['collective_training']
    for n in range(MIN_AGGREGATE):
        execute(env,'''INSERT INTO participants(action_id,last_name,first_name,created_at,active)
           VALUES(:a,:l,'Élève',:c,1)''',{'a':aid,'l':f'Stage{n}','c':utcnow_iso()})
    summary=client_action_summary(env,cl,aid)
    assert summary['collective_training'] and summary['participants_count']==MIN_AGGREGATE


def test_schedule_not_visible_for_small_or_individual_cohort(env):
    aid=action(env,'P4-2201');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN)
    assert client_public_schedule(env,cl,aid)==[]
    individual=action(env,'P4-2202','BILAN')
    grant_client_action(env,cl,individual,ADMIN)
    assert client_public_schedule(env,cl,individual)==[]


def test_different_action_different_accounts_are_isolated(env):
    aa=action(env,'P4-2301');bb=action(env,'P4-2302')
    a=client(env,'alpha');b=client(env,'beta')
    grant_client_action(env,a,aa,ADMIN);grant_client_action(env,b,bb,ADMIN)
    assert [x['id'] for x in list_client_actions(env,a)]==[aa]
    assert [x['id'] for x in list_client_actions(env,b)]==[bb]
    with pytest.raises(PermissionError):client_action_permission(env,a,bb)


def test_contract_go14_remains_closed(env):
    contract=client_go14_contract_snapshot()
    assert contract['competences_projets_go14']=='NOT_OPEN'
    assert contract['client_scope']=='EXPLICIT_PER_ACTION'
    assert contract['document_scope']=='EXPLICIT_PER_ACCOUNT'


def test_api_navigation_client_and_admin_preserve_three_original_portals():
    source=Path('app.py').read_text(encoding='utf8')
    nav=Path('navigation_p3.py').read_text(encoding='utf8')
    assert "?client_portal=1" in source
    assert 'client_invite' in source
    assert "_p3_sidebar_section('CLIENT'" in source
    assert "_run_ui_module('espace_client_drh_admin',admin_client_portal_screen)" in source
    assert 'CLIENT_SCREENS' in nav
    for key in ('CLIENT', 'BENEFICIARY', 'TRAINER', 'ADMIN_ACTION'):
        assert f"role == '{key}'" in nav
    assert 'teams_tab' in source and 'trainer_portal_page' in source and 'beneficiary_portal_page' in source


def test_admin_client_publish_requires_human_validation_check():
    source=Path('app.py').read_text(encoding='utf8')
    assert 'Vérification humaine de confidentialité obligatoire' in source
    assert "and d['publication_status']=='PUBLIE' and d['validation_status'] in ('VALIDE','FINALISE')" in source


def test_no_new_client_registry_created():
    db=Path('db.py').read_text(encoding='utf8')
    p4=db.split('CLIENT_PORTAL_SCHEMA = [',1)[1].split('I9A_SCHEMA = [',1)[0]
    assert 'client_portal_accounts' in p4
    assert 'client_action_grants' in p4
    assert 'crm_contact_id' in p4
    assert 'client_registry' not in p4
    assert 'invoice' not in p4


def test_client_old_published_version_survives_new_version_until_shared(env):
    aid=action(env,'P4-2401');cl=client(env)
    grant_client_action(env,cl,aid,ADMIN,can_download=True)
    r1,_,_=create_client_delivery(env,aid,b'v1','justif.pdf',ADMIN)
    set_document_validation(env,r1,'VALIDE',ADMIN);set_document_publication(env,r1,True,ADMIN)
    share_client_document(env,r1,cl,ADMIN)
    r2,_,_=create_client_delivery(env,aid,b'v2','justif.pdf',ADMIN)
    # Brouillon: ancienne version publiée reste accessible.
    assert read_client_document(env,r1,cl,aid)==b'v1'
    set_document_validation(env,r2,'VALIDE',ADMIN)
    set_document_publication(env,r2,True,ADMIN)
    # Même après publication serveur, le bénéficiaire client conserve SA livraison v1
    # jusqu'à partage explicite de la nouvelle version.
    assert read_client_document(env,r1,cl,aid)==b'v1'
    with pytest.raises(PermissionError):read_client_document(env,r2,cl,aid)
    share_client_document(env,r2,cl,ADMIN)
    assert [d['id'] for d in list_client_documents(env,cl,aid)]==[r2]
    assert read_client_document(env,r2,cl,aid)==b'v2'
    with pytest.raises(PermissionError):read_client_document(env,r1,cl,aid)


def test_bilan_cannot_have_document_grant(env):
    aid=action(env,'P4-2501','BILAN DE COMPETENCES');cl=client(env)
    with pytest.raises(PermissionError):grant_client_action(env,cl,aid,ADMIN,can_download=True)
    with pytest.raises(PermissionError):grant_client_action(env,cl,aid,ADMIN,can_upload=True)
    grant_client_action(env,cl,aid,ADMIN,can_download=False,can_upload=False)
    assert list_client_actions(env,cl)[0]['id']==aid


def test_five_failed_logins_temporarily_lock_account(env):
    cl=client(env,'locked')
    for i in range(5):
        assert verify_client_login(env,'locked@example.com','wrong') is None
    attempts=one(env,'SELECT failed_count,locked_until FROM client_login_attempts')
    assert attempts['failed_count']==5 and attempts['locked_until']
    assert verify_client_login(env,'locked@example.com',GOOD_PASSWORD) is None
    execute(env,"UPDATE client_login_attempts SET locked_until='2020-01-01T00:00:00+00:00'")
    assert verify_client_login(env,'locked@example.com',GOOD_PASSWORD)
    assert one(env,'SELECT COUNT(*) n FROM client_login_attempts')['n']==0


def test_crm_email_reconciliation_requires_new_authorizations(env):
    from client_portal import reconcile_client_contact_email
    aid=action(env,'P4-2601')
    cl=client(env,'change')
    grant_client_action(env,cl,aid,ADMIN,can_download=True)
    session=create_session(env,'CLIENT',cl)
    execute(env,"UPDATE crm_contacts SET email='new-change@example.com' WHERE email='change@example.com'")
    with pytest.raises(PermissionError):list_client_actions(env,cl)
    assert reconcile_client_contact_email(env,cl,ADMIN)=='new-change@example.com'
    assert resolve_session(env,session,expected_type='CLIENT') is None
    assert verify_client_login(env,'change@example.com',GOOD_PASSWORD) is None
    assert verify_client_login(env,'new-change@example.com',GOOD_PASSWORD) is None
    token=issue_client_access_token(env,cl,ADMIN)
    redeem_client_access_token(env,token,'NewPasswordSafe_2026!')
    assert verify_client_login(env,'new-change@example.com','NewPasswordSafe_2026!')
    assert list_client_actions(env,cl)==[]


def test_admin_lists_and_revokes_explicit_document_recipient(env):
    from client_portal import list_admin_client_document_shares
    aid=action(env,'P4-2701');a=client(env,'alpha');b=client(env,'beta')
    for cl in (a,b):grant_client_action(env,cl,aid,ADMIN,can_download=True)
    ref,_,_=create_client_delivery(env,aid,b'proof','resultat.pdf',ADMIN)
    set_document_validation(env,ref,'VALIDE',ADMIN);set_document_publication(env,ref,True,ADMIN)
    share_client_document(env,ref,a,ADMIN)
    shares=list_admin_client_document_shares(env,ref,ADMIN)
    assert [r['account_id'] for r in shares]==[a]
    with pytest.raises(PermissionError):list_admin_client_document_shares(env,ref,'unknown@other.fr')
    revoke_client_document(env,ref,a,ADMIN)
    assert list_admin_client_document_shares(env,ref,ADMIN)[0]['revoked_at']
    assert not list_client_documents(env,a,aid)
    assert not list_client_documents(env,b,aid)


def test_archived_crm_contact_blocks_client_identity_and_new_provisioning(env):
    aid=action(env,'P4-ARCHIVED')
    cid=contact(env,'archivedcontact')
    account=create_client_portal_account(env,cid,ADMIN)
    activate(env,account)
    grant_client_action(env,account,aid,ADMIN,can_download=True)
    assert client_action_summary(env,account,aid)['id']==aid
    execute(env,"UPDATE crm_contacts SET status='ARCHIVE' WHERE id=:i",{'i':cid})
    with pytest.raises(PermissionError):client_portal_identity(env,account)
    with pytest.raises(PermissionError):client_action_summary(env,account,aid)
    second=contact(env,'archivedsecond')
    execute(env,"UPDATE crm_contacts SET status='ARCHIVE' WHERE id=:i",{'i':second})
    with pytest.raises(PermissionError):create_client_portal_account(env,second,ADMIN)


def test_client_download_is_audited_without_exposing_bytes(env):
    aid=action(env,'P4-TRACE-DOC');account=client(env)
    grant_client_action(env,account,aid,ADMIN,can_download=True)
    doc,_,_=create_client_delivery(env,aid,b'jutfy','justificatif.pdf',ADMIN)
    set_document_validation(env,doc,'VALIDE',ADMIN)
    set_document_publication(env,doc,True,ADMIN)
    share_client_document(env,doc,account,ADMIN)
    assert read_client_document(env,doc,account,aid)==b'jutfy'
    # Le journal d'audit doit tracer la remise sans inclure le contenu du document.
    row=one(env,"SELECT * FROM audit_log WHERE event_type='CLIENT_DOCUMENT_DOWNLOADED' ORDER BY id DESC LIMIT 1")
    assert row is not None
    assert b'jutfy' not in str(row).encode()
