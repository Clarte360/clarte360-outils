"""J7: atomic donor/client link, multi-action portal summaries and ACL."""
from pathlib import Path
from datetime import datetime
import pytest
from db import make_engine, init_db, execute, one, q, utcnow_iso
from services import (create_action, create_action_with_client, create_crm_contact,
    action_ordering_client, link_action_ordering_client, link_crm_contact_action,
    unlink_crm_contact_action, create_beneficiary, add_participant, link_participant_to_beneficiary)
from client_portal import (create_client_portal_account, issue_client_access_token, redeem_client_access_token,
                           grant_client_action, revoke_client_action)
from portal_dashboard import beneficiary_dashboard, client_dashboard

ADMIN='admin-j7@clarte360.com'

@pytest.fixture
def e(tmp_path):
    engine=make_engine('sqlite:///'+str(tmp_path/'j7.db'));init_db(engine)
    execute(engine,"INSERT INTO admins(email,password_hash,role,active,created_at) VALUES(:a,'fake','ADMIN',1,:d)",{'a':ADMIN,'d':utcnow_iso()})
    return engine


def action_data(no):
    return dict(action_no=no,title='Bilan ou formation '+no,subtitle=None,nature='Formation',mode='INTRA',
        delivery_mode='PRESENTIEL',client_name='Nom libre obsolète',client_type='Non précisé',
        group_code=None,planned_hours=7,expected_participants=4,admin_email=ADMIN,trainer_name=None,
        trainer_email=None,location=None,notes=None,source='SAISIE')


def contact(e,num='A',company='Client test J7'):
    return create_crm_contact(e,'Camille',num,f'{num.lower()}-j7@example.org',company=company)


def enrollment(e,aid,email='benef-j7@example.org'):
    bid=create_beneficiary(e,'Test','Alex','2000-01-01',email=email)
    pid,_=add_participant(e,aid,{'individual_action_no':None,'last_name':'Test','first_name':'Alex','birth_date':'2000-01-01',
        'email':email,'company_name':None,'phone':None},ADMIN)
    link_participant_to_beneficiary(e,pid,bid,ADMIN)
    return bid,pid


def activated_client(e, cid):
    account=create_client_portal_account(e,cid,ADMIN)
    token=issue_client_access_token(e,account,ADMIN)
    redeem_client_access_token(e,token,'MonMotDePasseComplexe2026!')
    return account


def test_existing_client_link_is_atomic_and_has_no_permissions(e):
    c=contact(e)
    aid=create_action_with_client(e,action_data('J7-001'),ADMIN,crm_contact_id=c['id'])
    ac=action_ordering_client(e,aid)
    assert ac['crm_contact_id']==c['id']
    assert ac['customer_ref']=='CRM0:'+c['public_id']
    assert one(e,'SELECT client_name FROM actions WHERE id=:i',{'i':aid})['client_name']=='Client test J7'
    assert one(e,'SELECT COUNT(*) n FROM crm_action_links WHERE action_id=:i',{'i':aid})['n']==1
    assert q(e,'SELECT * FROM client_action_grants')==[]
    assert q(e,'SELECT * FROM client_portal_accounts')==[]


def test_created_contact_and_action_are_one_transaction(e):
    aid=create_action_with_client(e,action_data('J7-002'),ADMIN,new_crm_contact={
        'first_name':'Zoé','last_name':'Martin','email':'zoe-j7@example.org','company':'Entreprise Zoé'})
    x=action_ordering_client(e,aid)
    assert x['customer_ref'].startswith('CRM0:CRM-') and x['company']=='Entreprise Zoé'
    assert one(e,'SELECT COUNT(*) n FROM crm_contacts')['n']==1
    assert one(e,'SELECT COUNT(*) n FROM actions')['n']==1


def test_invalid_new_contact_does_not_orphan_action(e):
    with pytest.raises(ValueError):create_action_with_client(e,action_data('J7-003'),ADMIN,new_crm_contact={
        'first_name':'','last_name':'Martin','email':'incorrect','company':'Entreprise'})
    assert one(e,'SELECT COUNT(*) n FROM actions')['n']==0
    assert one(e,'SELECT COUNT(*) n FROM crm_contacts')['n']==0


def test_invalid_existing_contact_does_not_orphan_action(e):
    with pytest.raises(ValueError):create_action_with_client(e,action_data('J7-004'),ADMIN,crm_contact_id=1234)
    assert one(e,'SELECT COUNT(*) n FROM actions')['n']==0


def test_customer_identity_mandatory(e):
    with pytest.raises(ValueError):create_action_with_client(e,action_data('J7-005'),ADMIN)
    assert one(e,'SELECT COUNT(*) n FROM actions')['n']==0


def test_duplicated_no_clar_refuses_any_new_record_on_import_replay(e):
    c=contact(e)
    create_action_with_client(e,action_data('J7-006'),ADMIN,crm_contact_id=c['id'])
    with pytest.raises(ValueError):create_action_with_client(e,action_data('J7-006'),ADMIN,new_crm_contact={
        'first_name':'Jamais','last_name':'Créée','email':'replay@example.org'})
    assert one(e,'SELECT COUNT(*) n FROM actions')['n']==1
    assert one(e,'SELECT COUNT(*) n FROM action_ordering_clients')['n']==1
    assert one(e,'SELECT COUNT(*) n FROM crm_contacts')['n']==1


def test_schema_migration_is_idempotent(e):
    c=contact(e);aid=create_action_with_client(e,action_data('J7-007'),ADMIN,crm_contact_id=c['id'])
    init_db(e);init_db(e)
    assert one(e,'SELECT COUNT(*) n FROM action_ordering_clients WHERE action_id=:a',{'a':aid})['n']==1


def test_legacy_unique_crm_client_link_backfilled(e):
    c=contact(e);aid=create_action(e,action_data('J7-008'),ADMIN)
    execute(e,"INSERT INTO crm_action_links(contact_id,action_id,role,created_by,created_at) VALUES(:c,:a,'CLIENT',:by,:at)",
        {'c':c['id'],'a':aid,'by':ADMIN,'at':utcnow_iso()})
    assert action_ordering_client(e,aid) is None
    init_db(e)
    assert action_ordering_client(e,aid)['customer_ref']=='CRM0:'+c['public_id']


def test_ambiguous_legacy_clients_must_not_be_guessed(e):
    c1=contact(e,'AA');c2=contact(e,'BB');aid=create_action(e,action_data('J7-009'),ADMIN)
    for c in (c1,c2):
        execute(e,"INSERT INTO crm_action_links(contact_id,action_id,role,created_by,created_at) VALUES(:c,:a,'CLIENT',:by,:at)",
            {'c':c['id'],'a':aid,'by':ADMIN,'at':utcnow_iso()})
    init_db(e)
    assert action_ordering_client(e,aid) is None


def test_manual_link_primary_can_be_added_once(e):
    c1=contact(e,'AA');c2=contact(e,'BB');aid=create_action(e,action_data('J7-010'),ADMIN)
    link_crm_contact_action(e,c1['id'],aid,'CLIENT',ADMIN)
    assert action_ordering_client(e,aid)['crm_contact_id']==c1['id']
    link_crm_contact_action(e,c2['id'],aid,'CLIENT',ADMIN)
    assert action_ordering_client(e,aid)['crm_contact_id']==c1['id']
    assert one(e,'SELECT COUNT(*) n FROM crm_action_links WHERE action_id=:a',{'a':aid})['n']==2
    with pytest.raises(ValueError):link_action_ordering_client(e,aid,c2['id'],ADMIN)


def test_unlink_primary_removes_donor_reference_not_action(e):
    c=contact(e);aid=create_action_with_client(e,action_data('J7-011'),ADMIN,crm_contact_id=c['id'])
    unlink_crm_contact_action(e,c['id'],aid,ADMIN)
    assert action_ordering_client(e,aid) is None
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':aid}) is not None


def test_delete_fictional_action_cascades_customer_ref(e):
    c=contact(e);aid=create_action_with_client(e,action_data('J7-012'),ADMIN,crm_contact_id=c['id'])
    execute(e,'DELETE FROM actions WHERE id=:a',{'a':aid})
    assert action_ordering_client(e,aid) is None
    assert one(e,'SELECT COUNT(*) n FROM crm_contacts')['n']==1


def test_customer_link_alone_never_grants_client_portal(e):
    c=contact(e);aid=create_action_with_client(e,action_data('J7-013'),ADMIN,crm_contact_id=c['id'])
    acc=activated_client(e,c['id'])
    assert client_dashboard(e,acc)['actions']==[]
    grant_client_action(e,acc,aid,ADMIN,'PRESCRIPTEUR')
    assert len(client_dashboard(e,acc)['actions'])==1
    revoke_client_action(e,acc,aid,ADMIN)
    assert client_dashboard(e,acc)['actions']==[]


def test_client_dashboard_never_leaks_beneficiary_personal_data(e):
    c=contact(e);aid=create_action_with_client(e,action_data('J7-014'),ADMIN,crm_contact_id=c['id'])
    enroll=enrollment(e,aid,'confidential-person@example.org')
    acc=activated_client(e,c['id'])
    grant_client_action(e,acc,aid,ADMIN,'PRESCRIPTEUR')
    x=client_dashboard(e,acc)
    assert 'confidential-person@example.org' not in repr(x)
    assert 'Alex' not in repr(x)
    assert 'reports' not in x
    assert x['shared_documents']==0


def test_beneficiary_dashboard_shows_only_enrolled_actions(e):
    a1=create_action(e,action_data('J7-015'),ADMIN)
    a2=create_action(e,action_data('J7-016'),ADMIN)
    bid,_=enrollment(e,a1)
    data=beneficiary_dashboard(e,bid)
    assert [a['id'] for a in data['actions']]==[a1]
    assert all(r['action_id']!=a2 for r in data['upcoming'])
    assert data['signatures_to_review']==0


def test_beneficiary_upcoming_and_signature_require_own_participation(e):
    a1=create_action(e,action_data('J7-017'),ADMIN)
    a2=create_action(e,action_data('J7-018'),ADMIN)
    bid,pid=enrollment(e,a1)
    for aid,day in [(a1,'2026-10-15'),(a2,'2026-10-15'),(a1,'2026-10-01')]:
        execute(e,"INSERT INTO slots(action_id,slot_date,start_time,end_time,status,created_at,updated_at) VALUES(:a,:d,'10:00','11:00','PREVU',:n,:n)",
            {'a':aid,'d':day,'n':utcnow_iso()})
    dash=beneficiary_dashboard(e,bid,today='2026-10-10T12:00:00')
    assert len(dash['upcoming'])==1 and dash['upcoming'][0]['action_id']==a1
    assert dash['signatures_to_review']==1


def test_client_multi_role_is_separate_from_beneficiary_identity(e):
    c=contact(e);aid=create_action_with_client(e,action_data('J7-019'),ADMIN,crm_contact_id=c['id'])
    ben,_=enrollment(e,aid,c['email'])
    acc=activated_client(e,c['id'])
    assert len(beneficiary_dashboard(e,ben)['actions'])==1
    assert client_dashboard(e,acc)['actions']==[]


def test_ui_keeps_four_portal_guards_and_reuses_existing_client_grants():
    root=Path(__file__).resolve().parents[1]
    src=(root/'app.py').read_text(encoding='utf-8')
    assert 'create_action_with_client(ENGINE' in src
    assert 'Un donneur d’ordre et un contact de référence sont obligatoires' in src
    assert 'action_ordering_client(ENGINE,a[' in src
    assert "p4_admin_client_section']='Habilitations par action'" in src
    assert 'beneficiary_dashboard(ENGINE,bid)' in src
    assert 'client_dashboard(ENGINE,account_id)' in src
    assert '_j4_notification_drawer' in src
    assert 'client_action_summary(ENGINE,account_id,selected_action_id)' in src
    assert 'list_beneficiary_documents(ENGINE,bid)' in src

def test_email_collision_requires_existing_contact_selection(e):
    c=contact(e)
    with pytest.raises(ValueError,match='existe déjà'):
        create_action_with_client(e,action_data('J7-020'),ADMIN,new_crm_contact={
            'first_name':'Camille','last_name':'Autre','email':c['email'],'company':'Autre client'})
    assert one(e,'SELECT COUNT(*) n FROM actions')['n']==0
    assert one(e,'SELECT COUNT(*) n FROM crm_contacts')['n']==1


def test_crm_and_action_are_rolled_back_if_link_insert_fails(e):
    execute(e,"""CREATE TRIGGER forbid_j7_customer BEFORE INSERT ON action_ordering_clients
        BEGIN SELECT RAISE(ABORT,'synthetic failed link'); END""")
    with pytest.raises(Exception):
        create_action_with_client(e,action_data('J7-021'),ADMIN,new_crm_contact={
            'first_name':'Sophie','last_name':'Test','email':'rollback-j7@example.org',
            'company':'Entreprise fictive'})
    assert one(e,'SELECT COUNT(*) n FROM actions')['n']==0
    assert one(e,'SELECT COUNT(*) n FROM crm_contacts')['n']==0
    assert one(e,'SELECT COUNT(*) n FROM crm_events')['n']==0
