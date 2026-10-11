"""J4 automated checks. Only synthetic users, no network, no SMTP, no VPS."""
import pytest
from db import make_engine,init_db,execute,one,q,utcnow_iso
from security import hash_password
from services import (create_beneficiary_report,create_trainer_report,list_quality_events,
    add_quality_case_message,update_quality_event,quality_portal_thread,add_quality_event_action)
from workspace_notifications import (enqueue,inbox,mark_read,bind_external_identity,
    ingest_partner_event,document_available,document_needs_review,
    client_document_shared,schedule_changed)
ADMIN='administrator-j4@example.invalid'

@pytest.fixture
def env(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'notifications.db'));init_db(e)
    n=utcnow_iso()
    execute(e,'INSERT INTO admins(email,password_hash,created_at) VALUES(:e,:p,:n)',{'e':ADMIN,'p':hash_password('fictitious-only-password'),'n':n})
    a=[]
    for code in ('TEST-J4-A','TEST-J4-B'):
        a.append(execute(e,"""INSERT INTO actions(action_no,title,nature,mode,planned_hours,status,created_at,updated_at)
          VALUES(:c,'Formation fictive','FORMATION','INTRA',10,'ACTIVE',:n,:n)""",{'c':code,'n':n}))
    t=execute(e,"INSERT INTO trainers(full_name,email,created_at,updated_at) VALUES('Trainer Test','trainer-j4@example.invalid',:n,:n)",{'n':n})
    execute(e,'UPDATE actions SET trainer_id=:t WHERE id=:a',{'t':t,'a':a[0]})
    b=execute(e,"INSERT INTO beneficiaries(public_id,last_name,first_name,birth_date,created_at,updated_at) VALUES('BEN-J4','Test','Beneficiary','2001-01-01',:n,:n)",{'n':n})
    execute(e,"INSERT INTO beneficiary_portal_accounts(beneficiary_id,email,active,created_at,updated_at) VALUES(:b,'beneficiary-j4@example.invalid',1,:n,:n)",{'b':b,'n':n})
    execute(e,"INSERT INTO participants(action_id,last_name,first_name,beneficiary_id,created_at) VALUES(:a,'Test','Beneficiary',:b,:n)",{'a':a[0],'b':b,'n':n})
    c=execute(e,"INSERT INTO crm_contacts(public_id,first_name,last_name,email,created_at,updated_at) VALUES('CRM-J4','Fictive','Client','client-j4@example.invalid',:n,:n)",{'n':n})
    client=execute(e,"INSERT INTO client_portal_accounts(crm_contact_id,email,created_at,updated_at) VALUES(:i,'client-j4@example.invalid',:n,:n)",{'i':c,'n':n})
    execute(e,"INSERT INTO client_action_grants(account_id,action_id,role,can_download,can_upload,granted_at,granted_by) VALUES(:c,:a,'CLIENT_ADMIN',1,1,:n,:by)",{'c':client,'a':a[0],'n':n,'by':ADMIN})
    yield e,a,t,b,client
    e.dispose()

def test_schema_additive_idempotent(env):
    e,*_=env;init_db(e);init_db(e)
    assert one(e,"SELECT name FROM sqlite_master WHERE name='workspace_notifications'")
    assert one(e,"SELECT name FROM sqlite_master WHERE name='external_notification_identity_links'")

def test_new_beneficiary_report_alerts_admin_only(env):
    e,a,t,b,c=env
    create_beneficiary_report(e,a[0],b,'Observation','Confidential headline','Private details')
    notes=inbox(e,'ADMIN',ADMIN)
    assert len(notes)==1 and notes[0]['target_kind']=='QUALITY'
    assert 'Confidential' not in notes[0]['display_text']
    assert not inbox(e,'TRAINER',t)
    assert not inbox(e,'BENEFICIARY',b)

def test_quality_reply_and_status_notify_only_author(env):
    e,a,t,b,c=env
    create_beneficiary_report(e,a[0],b,'Observation','Private','Private')
    ev=list_quality_events(e,a[0])[0]
    add_quality_case_message(e,ev['id'],ADMIN,'First response','VERS_BENEFICIAIRE')
    add_quality_case_message(e,ev['id'],ADMIN,'Second response','VERS_BENEFICIAIRE')
    update_quality_event(e,ev['id'],ADMIN,status='EN_TRAITEMENT')
    msg=inbox(e,'BENEFICIARY',b)
    assert len(msg)==3
    assert {m['event_code'] for m in msg}=={'QUALITY_REPLY','QUALITY_STATUS'}
    assert not inbox(e,'TRAINER',t)
    thread=quality_portal_thread(e,ev['id'],'BENEFICIARY',b)
    assert [x['message'] for x in thread['messages']]==['First response','Second response']
    with pytest.raises(PermissionError): quality_portal_thread(e,ev['id'],'TRAINER',t)

def test_internal_quality_note_never_visible_to_reporter(env):
    e,a,t,b,c=env
    create_beneficiary_report(e,a[0],b,'Observation','Private','Private')
    ev=list_quality_events(e,a[0])[0]
    add_quality_case_message(e,ev['id'],ADMIN,'SECRET INTERNAL NOTE','INTERNE')
    assert quality_portal_thread(e,ev['id'],'BENEFICIARY',b)['messages']==[]
    assert not inbox(e,'BENEFICIARY',b)

def test_trainer_reply_with_link_and_permission(env):
    e,a,t,b,c=env
    create_trainer_report(e,a[0],t,'Observation','Private','Private')
    ev=list_quality_events(e,a[0])[0]
    add_quality_case_message(e,ev['id'],ADMIN,'For trainer','VERS_INTERVENANT')
    assert len(inbox(e,'TRAINER',t))==1
    assert quality_portal_thread(e,ev['id'],'TRAINER',t)['messages'][0]['message']=='For trainer'
    execute(e,'UPDATE actions SET trainer_id=NULL WHERE id=:a',{'a':a[0]})
    assert not inbox(e,'TRAINER',t)

def test_opening_notification_does_not_change_quality_status(env):
    e,a,t,b,c=env
    create_beneficiary_report(e,a[0],b,'Observation','Test','Text')
    event=list_quality_events(e,a[0])[0]
    note=inbox(e,'ADMIN',ADMIN)[0]
    assert mark_read(e,note['id'],'ADMIN',ADMIN)
    assert not inbox(e,'ADMIN',ADMIN)
    assert one(e,'SELECT status FROM quality_events WHERE id=:i',{'i':event['id']})['status']=='NOUVEAU'
    assert not mark_read(e,note['id'],'ADMIN',ADMIN)
    assert len(inbox(e,'ADMIN',ADMIN,unread_only=False))==1

def test_notifications_cannot_be_read_across_roles(env):
    e,a,t,b,c=env
    create_beneficiary_report(e,a[0],b,'Observation','Test','Text')
    n=inbox(e,'ADMIN',ADMIN)[0]
    with pytest.raises(PermissionError):mark_read(e,n['id'],'TRAINER',t)
    with pytest.raises(PermissionError):mark_read(e,n['id'],'ADMIN','bad-j4@example.invalid')

def test_idempotent_even_with_retries(env):
    e,a,t,b,c=env
    payload=dict(source_system='GDA',source_event_id='fixture-1',recipient_role='TRAINER',recipient_key=t,
        action_id=a[0],event_code='PLANNING_CHANGED',category='INFO',target_kind='ACTION',target_id=a[0],display_text='Planning mis à jour')
    assert enqueue(e,**payload)
    assert enqueue(e,**payload) is False
    assert len(inbox(e,'TRAINER',t))==1

def test_different_actions_not_transferred(env):
    e,a,t,b,c=env
    assert not enqueue(e,source_system='GDA',source_event_id='not-allowed',recipient_role='TRAINER',recipient_key=t,
        action_id=a[1],event_code='PLANNING_CHANGED',category='INFO',target_kind='ACTION',target_id=a[1],display_text='Planning')
    assert not inbox(e,'TRAINER',t)

def test_planning_changed_notifies_assigned_trainer_and_beneficiary_not_client(env):
    e,a,t,b,c=env
    assert schedule_changed(e,a[0],5,678)==2
    assert schedule_changed(e,a[0],5,678)==0
    assert len(inbox(e,'TRAINER',t))==1
    assert len(inbox(e,'BENEFICIARY',b))==1
    assert not inbox(e,'CLIENT',c)

def test_quality_capa_alert_and_source_not_revealed_to_client(env):
    e,a,t,b,c=env
    create_beneficiary_report(e,a[0],b,'Observation','Private','Private')
    ev=list_quality_events(e,a[0])[0]
    add_quality_event_action(e,ev['id'],'Correction',ADMIN)
    admin=inbox(e,'ADMIN',ADMIN)
    assert {x['event_code'] for x in admin}=={'QUALITY_NEW','QUALITY_CAPA'}
    assert not inbox(e,'CLIENT',c)

def _doc(e,action_id):
    from db import utcnow_iso
    n=utcnow_iso()
    file=execute(e,"INSERT INTO stored_files(sha256,storage_path,size_bytes,created_at) VALUES(:h,'/tmp/fictional-not-existing',10,:n)",{'h':f'fictional-{action_id}-{n}','n':n})
    return execute(e,"""INSERT INTO document_references(stored_file_id,action_id,category,display_name,audience,publication_status,validation_status,created_at,uploaded_by)
          VALUES(:f,:a,'JUSTIFICATIF_CLIENT','Confidential file name','CLIENT_ONLY','PUBLIE','VALIDE',:n,'administrator-j4@example.invalid')""",{'f':file,'a':action_id,'n':n})

def test_document_admin_review_alert_without_document_title(env):
    e,a,t,b,c=env
    d=_doc(e,a[0]);document_needs_review(e,d,a[0],f'beneficiary:{b}')
    notes=inbox(e,'ADMIN',ADMIN)
    assert len(notes)==1
    assert notes[0]['display_text']=='Document déposé : validation à effectuer'
    assert notes[0]['category']=='ACTION'

def test_share_client_before_activation_survives_until_login(env):
    e,a,t,b,c=env
    d=_doc(e,a[0]);now=utcnow_iso()
    execute(e,'INSERT INTO client_document_shares(document_reference_id,account_id,published_at,published_by) VALUES(:d,:c,:n,:by)',{'d':d,'c':c,'n':now,'by':ADMIN})
    assert client_document_shared(e,d,c,a[0])
    assert not inbox(e,'CLIENT',c)
    execute(e,"UPDATE client_portal_accounts SET password_hash='activation-mock' WHERE id=:i",{'i':c})
    # Actual file authorization is checked again on first login.
    notes=inbox(e,'CLIENT',c)
    assert len(notes)==1 and notes[0]['target_kind']=='DOCUMENT'
    assert mark_read(e,notes[0]['id'],'CLIENT',c)

def test_revoked_client_action_hides_alert(env):
    e,a,t,b,c=env
    execute(e,"UPDATE client_portal_accounts SET password_hash='activation-mock' WHERE id=:i",{'i':c})
    assert enqueue(e,source_system='GDA',source_event_id='client1',recipient_role='CLIENT',recipient_key=c,action_id=a[0],event_code='CLIENT_UPDATE',category='INFO',target_kind='ACTION',target_id=a[0],display_text='Dossier actualisé')
    notes=inbox(e,'CLIENT',c);assert len(notes)==1
    execute(e,'UPDATE client_action_grants SET revoked_at=:n WHERE account_id=:c',{'n':utcnow_iso(),'c':c})
    assert not inbox(e,'CLIENT',c)
    with pytest.raises(PermissionError):mark_read(e,notes[0]['id'],'CLIENT',c)

def test_external_event_contract_requires_authenticated_connector_and_mapping(env):
    e,a,t,b,c=env
    execute(e,"UPDATE client_portal_accounts SET password_hash='activation-mock' WHERE id=:i",{'i':c})
    ev={'version':1,'source_system':'GESTION_CLIENTS','event_id':'CRM17-EV-42','action_no':'TEST-J4-A',
        'recipient':{'subject_type':'CRM17_CONTACT','subject_id':'X42','role':'CLIENT'},'type':'CLIENT_UPDATE'}
    with pytest.raises(PermissionError):ingest_partner_event(e,ev,authenticated_source=None)
    assert not ingest_partner_event(e,ev,authenticated_source='GESTION_CLIENTS')
    assert bind_external_identity(e,'GESTION_CLIENTS','CRM17_CONTACT','X42','CLIENT',c,admin_email=ADMIN)
    assert ingest_partner_event(e,ev,authenticated_source='GESTION_CLIENTS')
    assert not ingest_partner_event(e,ev,authenticated_source='GESTION_CLIENTS')
    assert len(inbox(e,'CLIENT',c))==1

def test_external_event_rejects_unknown_version_or_source(env):
    e,a,t,b,c=env
    good={'version':1,'source_system':'GESTION_CLIENTS','event_id':'x1','action_no':'TEST-J4-A',
        'recipient':{'subject_type':'CRM17_CONTACT','subject_id':'X','role':'CLIENT'},'type':'CLIENT_UPDATE'}
    with pytest.raises(ValueError):ingest_partner_event(e,{**good,'version':2},authenticated_source='GESTION_CLIENTS')
    with pytest.raises(ValueError):ingest_partner_event(e,{**good,'source_system':'GDA'},authenticated_source='GESTION_CLIENTS')
    with pytest.raises(ValueError):ingest_partner_event(e,{**good,'type':'RAW_BILAN_RESULTS'},authenticated_source='GESTION_CLIENTS')

def test_no_secrets_pii_in_notification_text(env):
    e,a,t,b,c=env
    assert enqueue(e,source_system='GDA',source_event_id='private-1',recipient_role='TRAINER',recipient_key=t,
        action_id=a[0],event_code='PLANNING_CHANGED',category='INFO',target_kind='ACTION',target_id=a[0],display_text='Horaire modifié')
    row=one(e,"SELECT * FROM workspace_notifications WHERE source_event_id='private-1'")
    assert row['display_text']=='Horaire modifié' and 'private' not in row['display_text'].lower()

def test_action_deleted_cascades_notifications(env):
    e,a,t,b,c=env
    assert schedule_changed(e,a[0],4,45)==2
    execute(e,'DELETE FROM actions WHERE id=:i',{'i':a[0]})
    assert not q(e,'SELECT * FROM workspace_notifications')

def test_admin_without_action_sees_orphan_quality_case_alert(env):
    e,a,t,b,c=env
    from services import create_quality_event
    event=create_quality_event(e,'EXPRESSION','OBSERVATION','Orphan fiction','not attached',ADMIN,action_id=None)
    notes=inbox(e,'ADMIN',ADMIN)
    assert len(notes)==1 and notes[0]['target_id']==str(event)

def test_role_restrictions_for_quality_and_document(env):
    e,a,t,b,c=env
    create_beneficiary_report(e,a[0],b,'Observation','Issue','Private')
    event=list_quality_events(e,a[0])[0]
    assert not enqueue(e,source_system='GDA',source_event_id='secret-cl',recipient_role='CLIENT',recipient_key=c,
        action_id=a[0],event_code='QUALITY_STATUS',category='INFO',target_kind='QUALITY',target_id=event['id'],display_text='Case updated')
    assert not enqueue(e,source_system='GDA',source_event_id='secret-tr',recipient_role='TRAINER',recipient_key=t,
        action_id=a[0],event_code='QUALITY_STATUS',category='INFO',target_kind='QUALITY',target_id=event['id'],display_text='Case updated')

def test_published_beneficiary_upload_notifies_admin_without_email_opt_in(env,tmp_path,monkeypatch):
    import services
    e,a,t,b,c=env
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'blobs')
    services.BENEFICIARY_DOC_DIR.mkdir()
    from services import store_document_for_actor
    ref,_,_=store_document_for_actor(e,'BENEFICIARY',b,b'fictitious','fictitious.pdf',a[0])
    notice=inbox(e,'ADMIN',ADMIN)
    assert len(notice)==1 and notice[0]['event_code']=='DOCUMENT_AVAILABLE'
    assert notice[0]['target_id']==str(ref)
    assert 'fictitious.pdf' not in notice[0]['display_text']
    assert not inbox(e,'BENEFICIARY',b)

def test_notification_posted_for_published_file_does_not_duplicate_after_rerun(env,tmp_path,monkeypatch):
    import services
    e,a,t,b,c=env
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'blobs')
    services.BENEFICIARY_DOC_DIR.mkdir()
    from services import store_document_for_actor
    ref,_,_=store_document_for_actor(e,'BENEFICIARY',b,b'fictitious','fictitious.pdf',a[0])
    from workspace_notifications import document_received
    assert document_received(e,ref,a[0],f'beneficiary:{b}')==0
    assert len(inbox(e,'ADMIN',ADMIN))==1

def test_planning_notifications_are_independent_from_optional_email_dispatch(env):
    e,a,t,b,c=env
    from services import propagate_planning_change
    event=propagate_planning_change(e,a[0],None,'TEST_CHANGE','admin-test',details={'test_only':True})
    assert event>0
    assert {x['event_code'] for x in inbox(e,'BENEFICIARY',b)}=={'PLANNING_CHANGED'}
    assert {x['event_code'] for x in inbox(e,'TRAINER',t)}=={'PLANNING_CHANGED'}
    assert not inbox(e,'CLIENT',c)
    # Existing I4 mail hook is allowed to retry idempotently.
    assert schedule_changed(e,a[0],None,event)==0

def test_notification_target_must_match_action_identity(env):
    e,a,t,b,c=env
    with pytest.raises(ValueError,match='rattachement'):
        enqueue(e,source_system='GESTION_CLIENTS',source_event_id='malformed-action-id',
            recipient_role='TRAINER',recipient_key=t,action_id=a[0],event_code='CLIENT_UPDATE',
            category='INFO',target_kind='ACTION',target_id=a[1],display_text='Dossier actualisé')

def test_revocation_of_beneficiary_participation_hides_notification(env):
    e,a,t,b,c=env
    assert schedule_changed(e,a[0],None,123)==2
    msg=inbox(e,'BENEFICIARY',b)[0]
    execute(e,"UPDATE participants SET active=0 WHERE action_id=:a AND beneficiary_id=:b",{'a':a[0],'b':b})
    assert not inbox(e,'BENEFICIARY',b)
    with pytest.raises(PermissionError):mark_read(e,msg['id'],'BENEFICIARY',b)

def test_j1_purge_preview_includes_j4_inbox_and_removes_it(env,tmp_path):
    import purge_guard
    from services import purge_action
    e,a,t,b,c=env
    assert schedule_changed(e,a[0],None,590)==2
    assert len(q(e,'SELECT id FROM workspace_notifications WHERE action_id=:a',{'a':a[0]}))==2
    evidence='Uniquement des donnees fictives de recette sans obligation de conservation ni aucune piece reelle.'
    root=tmp_path/'purge_data';root.mkdir()
    cert=purge_guard.certify_test_action(e,a[0],ADMIN,evidence=evidence,
        confirmation='JE CERTIFIE ESSAI TEST-J4-A',password='fictitious-only-password',data_root=root)
    assert cert[0],cert
    preview=purge_guard.preview_action_purge(e,a[0],data_root=root)
    assert preview['counts']['workspace_notifications']==2
    ok,reason=purge_action(e,a[0],ADMIN,confirmation='SUPPRIMER ESSAI TEST-J4-A',
        preview_fingerprint=preview['fingerprint'],data_root=root)
    assert ok,reason
    assert not q(e,'SELECT id FROM workspace_notifications WHERE action_id=:a',{'a':a[0]})
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':a[1]})

def test_report_upload_10mb_ui_compatible_with_global_document_limit():
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/'app.py').read_text()
    conf=(Path(__file__).resolve().parents[1]/'.streamlit'/'config.toml').read_text()
    assert 'def _j4_report_file_uploader(' in src
    assert "options['max_upload_size']=10" in src
    assert "_j4_report_file_uploader('Joindre éventuellement un document (10 Mo max)'" in src
    assert 'maxUploadSize = 50' in conf  # Other existing upload workflows are preserved.
    assert 'up.size>10*1024*1024' in src
