"""J6: intervenant personal workspace, professional dossier segregation, tools safeguards."""
from pathlib import Path
import pytest
from db import init_db, make_engine, execute, q, one
import services
from services import (
    create_action, add_participant, create_beneficiary, link_participant_to_beneficiary,
    add_trainer, assign_action_trainer, set_action_trainer_prescription_permission,
    upsert_tool_catalog, set_action_tool_allowed, create_tool_prescription,
    trainer_tool_followup_choices, trainer_update_tool_followup, prescription_events,
    create_professional_intervenant, store_professional_document,
    set_professional_document_visibility, trainer_shared_professional_documents,
    trainer_shared_professional_document_bytes, set_professional_active,
)


def fixtures(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'j6_test.db'))
    init_db(e)
    aid=create_action(e,{'action_no':'J6-A01','title':'Formation fictive','nature':'FORMATION',
        'mode':'PRESENTIEL','client_name':'Client factice','client_type':'Entreprise',
        'subtitle':None,'group_code':None,'planned_hours':7,'expected_participants':1,
        'admin_email':'admin@test.fr','trainer_name':None,'trainer_email':None,
        'location':'Paris','notes':None,'source':'TEST'},'admin')
    part,_=add_participant(e,aid,{'last_name':'TEST','first_name':'Anne','email':'anna@example.org'},'admin')
    bid=create_beneficiary(e,'TEST','Anne','1990-01-01','anna@example.org',actor='admin')
    link_participant_to_beneficiary(e,part,bid,'admin')
    trainer=add_trainer(e,'Intervenant habilité','trainer-j6@example.org','','admin')
    other=add_trainer(e,'Intervenant non habilité','trainer-other@example.org','','admin')
    ok,_=assign_action_trainer(e,aid,trainer,'admin');assert ok
    ok,_=assign_action_trainer(e,aid,other,'admin');assert ok
    set_action_trainer_prescription_permission(e,aid,trainer,True,'admin')
    set_action_trainer_prescription_permission(e,aid,other,False,'admin')
    upsert_tool_catalog(e,{'tool_code':'J6_GENERIC','name':'Outil de démonstration',
          'base_url':'https://example.org','launch_type':'HUB_REDIRECT','connector_status':'LAUNCH_ONLY'},'admin')
    set_action_tool_allowed(e,aid,'J6_GENERIC',True,'admin')
    pr=create_tool_prescription(e,'J6_GENERIC',bid,aid,part,
        prescriber_type='ADMIN',prescriber_id='admin@example.org',actor='admin')
    return e,aid,trainer,other,pr


def test_j6_trainer_can_review_another_creators_prescription(tmp_path):
    e,aid,tid,other,pr=fixtures(tmp_path)
    assert 'A_REVOIR_EN_SEANCE' in trainer_tool_followup_choices(e,tid,pr['prescription_id'])
    res=trainer_update_tool_followup(e,tid,pr['prescription_id'],'A_REVOIR_EN_SEANCE')
    assert res['status']=='A_REVOIR_EN_SEANCE'
    assert trainer_tool_followup_choices(e,tid,pr['prescription_id'])==('REVU_EN_SEANCE',)
    new=trainer_update_tool_followup(e,tid,pr['prescription_id'],'REVU_EN_SEANCE')
    assert new['status']=='REVU_EN_SEANCE'
    history=prescription_events(e,pr['prescription_id'])
    assert [r['new_status'] for r in history][-2:]==['A_REVOIR_EN_SEANCE','REVU_EN_SEANCE']


def test_j6_trainer_without_permission_cannot_revise(tmp_path):
    e,aid,tid,other,pr=fixtures(tmp_path)
    assert trainer_tool_followup_choices(e,other,pr['prescription_id'])==()
    with pytest.raises(PermissionError):trainer_update_tool_followup(e,other,pr['prescription_id'],'REVU_EN_SEANCE')


def test_j6_rights_revocation_is_immediate(tmp_path):
    e,aid,tid,other,pr=fixtures(tmp_path)
    set_action_trainer_prescription_permission(e,aid,tid,False,'admin')
    assert trainer_tool_followup_choices(e,tid,pr['prescription_id'])==()
    with pytest.raises(PermissionError):trainer_update_tool_followup(e,tid,pr['prescription_id'],'REVU_EN_SEANCE')


def test_j6_no_status_escalation_to_technical_done(tmp_path):
    e,aid,tid,other,pr=fixtures(tmp_path)
    for status in ('TERMINE','CONSULTE','ENVOYE','ANNULE','EN_COURS'):
        with pytest.raises(PermissionError):trainer_update_tool_followup(e,tid,pr['prescription_id'],status)
    assert one(e,'SELECT status FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']})['status']=='A_FAIRE'


def test_j6_completed_prescription_immutable_in_trainer_ui(tmp_path):
    e,aid,tid,other,pr=fixtures(tmp_path)
    services.update_tool_prescription_status(e,pr['prescription_id'],'TERMINE','connector')
    assert trainer_tool_followup_choices(e,tid,pr['prescription_id'])==()


def test_j6_connected_external_tool_is_readonly(tmp_path):
    e,aid,tid,other,pr=fixtures(tmp_path)
    upsert_tool_catalog(e,{'tool_code':'J6_SIGNED','name':'Outil connecté',
          'base_url':'https://example.org','launch_type':'EXTERNAL_SIGNED','connector_status':'CONNECTED'},'admin')
    set_action_tool_allowed(e,aid,'J6_SIGNED',True,'admin')
    part=one(e,'SELECT id,beneficiary_id FROM participants WHERE action_id=:a',{'a':aid})
    signed=create_tool_prescription(e,'J6_SIGNED',part['beneficiary_id'],aid,part['id'],actor='admin')
    assert trainer_tool_followup_choices(e,tid,signed['prescription_id'])==()


def test_j6_action_permission_removed_blocks_tool_management(tmp_path):
    e,aid,tid,other,pr=fixtures(tmp_path)
    execute(e,'UPDATE action_tool_permissions SET allowed=0 WHERE action_id=:a AND tool_code=:c',{'a':aid,'c':'J6_GENERIC'})
    assert trainer_tool_followup_choices(e,tid,pr['prescription_id'])==()


def test_j6_foreign_action_cannot_be_modified(tmp_path):
    e,aid,tid,other,pr=fixtures(tmp_path)
    outsider=add_trainer(e,'Outside','outside-j6@example.org','','admin')
    with pytest.raises(PermissionError):trainer_update_tool_followup(e,outsider,pr['prescription_id'],'REVU_EN_SEANCE')


def test_j6_professional_documents_are_private_by_default(tmp_path,monkeypatch):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    e=make_engine('sqlite:///'+str(tmp_path/'docs.db'));init_db(e)
    p=create_professional_intervenant(e,'Dossier test J6',email='j6doc@example.org',actor='admin')
    tid=one(e,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':p})['trainer_id']
    d=store_professional_document(e,p,b'%PDF-1.4 internal','preuve.pdf','AUTRE',actor='admin')
    assert trainer_shared_professional_documents(e,tid)==[]
    with pytest.raises(PermissionError):trainer_shared_professional_document_bytes(e,tid,d)
    set_professional_document_visibility(e,p,d,'INTERVENANT','admin')
    items=trainer_shared_professional_documents(e,tid)
    assert [v['id'] for v in items]==[d]
    assert trainer_shared_professional_document_bytes(e,tid,d)['data']==b'%PDF-1.4 internal'
    set_professional_document_visibility(e,p,d,'INTERNE','admin')
    assert trainer_shared_professional_documents(e,tid)==[]
    with pytest.raises(PermissionError):trainer_shared_professional_document_bytes(e,tid,d)


def test_j6_other_intervenant_cannot_read_shared_doc(tmp_path,monkeypatch):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    e=make_engine('sqlite:///'+str(tmp_path/'docs_other.db'));init_db(e)
    a=create_professional_intervenant(e,'A dossier',email='a-doc@example.org',actor='admin')
    b=create_professional_intervenant(e,'B dossier',email='b-doc@example.org',actor='admin')
    ta=one(e,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':a})['trainer_id']
    tb=one(e,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':b})['trainer_id']
    d=store_professional_document(e,a,b'%PDF-1.4 confidential','doc.pdf','AUTRE',actor='admin')
    set_professional_document_visibility(e,a,d,'INTERVENANT','admin')
    assert trainer_shared_professional_document_bytes(e,ta,d)['name']=='doc.pdf'
    assert trainer_shared_professional_documents(e,tb)==[]
    with pytest.raises(PermissionError):trainer_shared_professional_document_bytes(e,tb,d)


def test_j6_inactive_person_or_trainer_cannot_read_doc(tmp_path,monkeypatch):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    e=make_engine('sqlite:///'+str(tmp_path/'docs_inactive.db'));init_db(e)
    p=create_professional_intervenant(e,'Dossier inactive',email='inact-doc@example.org',actor='admin')
    tid=one(e,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':p})['trainer_id']
    d=store_professional_document(e,p,b'%PDF-1.4 inactive','evidence.pdf','AUTRE',actor='admin')
    set_professional_document_visibility(e,p,d,'INTERVENANT','admin')
    set_professional_active(e,p,False,'admin','Test inactivation')
    assert trainer_shared_professional_documents(e,tid)==[]
    with pytest.raises(PermissionError):trainer_shared_professional_document_bytes(e,tid,d)


def test_j6_invalid_doc_visibility_rejected(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'visibility.db'));init_db(e)
    p=create_professional_intervenant(e,'Dossier ref',actor='admin')
    with pytest.raises(ValueError):set_professional_document_visibility(e,p,1,'PUBLIC','admin')


def test_j6_screen_structure_and_preserved_scope():
    app=Path(__file__).resolve().parents[1]/'app.py'
    src=app.read_text(encoding='utf-8')
    trainer=src[src.index('def trainer_portal_page():'):src.index('def beneficiary_invitation_page(')]
    assert "selected_view=='Accueil personnel'" not in trainer  # default branch
    assert "selected_view=='Mes interventions'" in trainer
    assert trainer.index("if selected_view=='Mes interventions':") < trainer.index("st.markdown('#### Suivi de mes émargements')")
    assert trainer.count("st.markdown('#### Suivi de mes émargements')")==1
    assert "trainer_shared_professional_documents(ENGINE,tid)" in trainer
    dossier=src[src.index('def _j6_professional_dossiers():'):src.index('def _j6_professional_pilotage():')]
    assert "if not selected:" in dossier
    assert "st.caption('Dossier unique : sept rubriques" in dossier
    assert "'Synthèse','Parcours professionnel','Conformité & collaboration','Analyse IA','Qualifications','Missions / Affectations','CV Clarté360'" in dossier
    assert "st.session_state.pop('j6_professional_selected'" in dossier
    pilotage=src[src.index('def _j6_professional_pilotage():'):src.index('def settings_screen():')]
    for tab in ('with sub_candidates:','with sub_matrix:','with sub_prestations:','with sub_alertes:'):
        assert tab in pilotage


def test_j6_shared_professional_document_notification_and_revocation(tmp_path,monkeypatch):
    from workspace_notifications import inbox,mark_read
    monkeypatch.setattr(services,'ROOT',tmp_path)
    e=make_engine('sqlite:///'+str(tmp_path/'doc_notification.db'));init_db(e)
    p=create_professional_intervenant(e,'Notified trainer',email='j6-notify@example.org',actor='admin')
    tid=one(e,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':p})['trainer_id']
    d=store_professional_document(e,p,b'%PDF-1.4 share','shared.pdf','AUTRE',actor='admin')
    assert inbox(e,'TRAINER',tid)==[]
    set_professional_document_visibility(e,p,d,'INTERVENANT','admin')
    notes=inbox(e,'TRAINER',tid)
    assert len(notes)==1 and notes[0]['target_kind']=='PROFESSIONAL_DOCUMENT'
    assert notes[0]['action_id'] is None
    assert 'shared.pdf' not in notes[0]['display_text']  # no personal filename in alert
    set_professional_document_visibility(e,p,d,'INTERNE','admin')
    assert inbox(e,'TRAINER',tid)==[]
    with pytest.raises(PermissionError):mark_read(e,notes[0]['id'],'TRAINER',tid)
    set_professional_document_visibility(e,p,d,'INTERVENANT','admin')
    notes2=inbox(e,'TRAINER',tid)
    assert len(notes2)==1 and notes2[0]['id']!=notes[0]['id']
    assert mark_read(e,notes2[0]['id'],'TRAINER',tid)
    assert inbox(e,'TRAINER',tid)==[]


def test_j6_completed_owned_prescription_cannot_be_cancelled(tmp_path):
    e,aid,tid,other,pr=fixtures(tmp_path)
    # Ownership remains checked; completion cannot be silently replaced by cancellation.
    from services import cancel_tool_prescription_owned
    execute(e, "UPDATE tool_prescriptions SET prescriber_type='TRAINER',prescriber_id=:t WHERE prescription_id=:p",
        {'t':str(tid),'p':pr['prescription_id']})
    services.update_tool_prescription_status(e,pr['prescription_id'],'TERMINE','connector')
    ok,msg=cancel_tool_prescription_owned(e,pr['prescription_id'],'TRAINER',tid,'trainer')
    assert not ok and 'finalisée' in msg
    assert one(e,'SELECT status FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']})['status']=='TERMINE'


def test_j6_admin_profile_file_sharing_notification_is_self_only(tmp_path,monkeypatch):
    from workspace_notifications import inbox
    monkeypatch.setattr(services,'ROOT',tmp_path)
    e=make_engine('sqlite:///'+str(tmp_path/'two_identities.db'));init_db(e)
    x=create_professional_intervenant(e,'Owner',email='j6owner@example.org',actor='admin')
    y=create_professional_intervenant(e,'Other',email='j6other@example.org',actor='admin')
    owner=one(e,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':x})['trainer_id']
    other=one(e,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':y})['trainer_id']
    d=store_professional_document(e,x,b'%PDF-1.4 self','staff.pdf','AUTRE',actor='admin')
    set_professional_document_visibility(e,x,d,'INTERVENANT','admin')
    assert len(inbox(e,'TRAINER',owner))==1
    assert inbox(e,'TRAINER',other)==[]
