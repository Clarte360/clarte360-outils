"""J8: no double legal/financial master, real action coverage and historical proofs."""
import json
import pytest
from db import make_engine, init_db, execute, one, q, utcnow_iso
from services import (create_action,create_action_with_client,create_crm_contact,activate_action,
    add_participant,add_trainer,assign_action_trainer,unassign_action_trainer,
    create_professional_intervenant,update_professional_profile,link_professional_supplier)
from mission_engagements import (action_mission_coverage,enable_action_mission_control,
    list_action_missions,list_trainer_missions,verify_mission_engagement,
    sync_mission_assignment,revise_mission,mission_outbox_pending,suspend_missions_for_trainer)

ADMIN='j8-admin@example.org'
DOC_DATE='2026-10-10T13:00:00+02:00'

@pytest.fixture
def env(tmp_path):
    engine=make_engine('sqlite:///'+str(tmp_path/'j8.db'))
    init_db(engine)
    execute(engine,"INSERT INTO admins(email,password_hash,role,active,created_at) VALUES(:a,'fake','ADMIN',1,:n)",{'a':ADMIN,'n':utcnow_iso()})
    c=create_crm_contact(engine,'Marie','Entreprise','marie@entreprise-j8.example',company='Entreprise test J8')
    return engine,c['id']


def new_action(e,cid,code='J8-001',mode='PRESENTIEL',new=True):
    d=dict(action_no=code,title='Action test '+code,subtitle=None,nature='FORMATION',mode='INTRA',
        delivery_mode=mode,client_name=None,client_type=None,group_code=None,planned_hours=2,
        expected_participants=1,admin_email=ADMIN,trainer_name=None,trainer_email=None,
        location=None,notes=None,source='RECETTE_FICTIVE_J8')
    aid=create_action_with_client(e,d,ADMIN,crm_contact_id=cid) if new else create_action(e,d,ADMIN)
    add_participant(e,aid,{'first_name':'Alice','last_name':'TEST','email':'alice-j8@example.org'},ADMIN)
    if mode=='ELEARNING':
        execute(e,'UPDATE actions SET use_attendance=0 WHERE id=:a',{'a':aid})
    else:
        now=utcnow_iso()
        execute(e,"""INSERT INTO slots(action_id,slot_date,start_time,end_time,created_at,updated_at)
           VALUES(:a,'2026-10-10','14:00','16:00',:n,:n)""",{'a':aid,'n':now})
    return aid


def person(e,name,kind='SALARIE'):
    p=create_professional_intervenant(e,name,actor=ADMIN,collaboration_type=kind)
    t=one(e,'SELECT trainer_id FROM professional_persons WHERE professional_person_id=:p',{'p':p})
    return p,t['trainer_id']


def verify(e,mid,**kwargs):
    return verify_mission_engagement(e,mid,ADMIN,document_ref=kwargs.pop('document_ref','DOC-VALIDE-J8'),
      document_version=kwargs.pop('document_version','v1'),accepted_at=kwargs.pop('accepted_at',DOC_DATE),**kwargs)


def test_schema_idempotent_and_separate_from_financial_master(env):
    e,c=env;init_db(e);init_db(e)
    assert one(e,"SELECT COUNT(*) n FROM sqlite_master WHERE type='table' AND name='action_mission_policy'")['n']==1
    cols={x['name'] for x in q(e,'PRAGMA table_info(action_mission_engagements)')}
    assert 'cost_commitment_ref' in cols and 'document_version' in cols and 'supplier_id' in cols
    assert 'invoice_id' not in cols and 'amount_to_pay' not in cols


def test_new_client_action_enforces_but_draft_allowed(env):
    e,c=env;a=new_action(e,c)
    assert one(e,'SELECT status FROM actions WHERE id=:a',{'a':a})['status']=='BROUILLON'
    assert action_mission_coverage(e,a)['mode']=='ENFORCE'
    ok,why=activate_action(e,a,ADMIN)
    assert not ok and any('Aucun intervenant' in x for x in why)
    assert one(e,'SELECT status FROM actions WHERE id=:a',{'a':a})['status']=='BROUILLON'


def test_legacy_actions_only_preview_until_admin_opt_in(env):
    e,c=env;a=new_action(e,c,new=False)
    assert action_mission_coverage(e,a)['mode']=='PREVIEW'
    ok,why=activate_action(e,a,ADMIN)
    assert ok and not why
    enable_action_mission_control(e,a,ADMIN)
    assert action_mission_coverage(e,a)['mode']=='ENFORCE'


def test_assignment_creates_exactly_one_stable_mission(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Salarié test')
    assert assign_action_trainer(e,a,t,ADMIN,is_referent=True)[0]
    initial=list_action_missions(e,a)
    assert len(initial)==1 and initial[0]['professional_person_id']==p
    sync_mission_assignment(e,a,t,ADMIN)
    assert len(list_action_missions(e,a))==1
    assert initial[0]['mission_id']==list_action_missions(e,a)[0]['mission_id']
    assert initial[0]['contract_kind']=='LETTRE_SALARIE'
    assert not action_mission_coverage(e,a)['ready']


def test_verified_salaried_mission_unlocks_new_action(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Salarié référent')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    m=list_action_missions(e,a)[0]
    verify(e,m['mission_id'])
    assert action_mission_coverage(e,a)['ready']
    ok,issues=activate_action(e,a,ADMIN)
    assert ok and not issues
    assert one(e,'SELECT status FROM actions WHERE id=:a',{'a':a})['status']=='ACTIVE'


def test_elearing_needs_real_followup_with_accepted_reference(env):
    e,c=env;a=new_action(e,c,'J8-EL','ELEARNING');p,t=person(e,'Référent à distance')
    assign_action_trainer(e,a,t,ADMIN,is_referent=False)
    mid=list_action_missions(e,a)[0]['mission_id']
    verify(e,mid)
    issues=action_mission_coverage(e,a)['issues']
    assert any('responsable' in x for x in issues)
    assert not activate_action(e,a,ADMIN)[0]
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    # The new coordination role must not silently reuse the earlier acceptance.
    assert not action_mission_coverage(e,a)['ready']
    new=list_action_missions(e,a,active_only=True)[0]
    assert new['mission_id']!=mid and new['status']=='A_PREPARER'
    verify(e,new['mission_id'],document_version='v2')
    assert action_mission_coverage(e,a)['ready']
    assert activate_action(e,a,ADMIN)[0]


def test_multiple_assigned_people_each_need_proof(env):
    e,c=env;a=new_action(e,c);p1,t1=person(e,'Formatrice principale');p2,t2=person(e,'Cointervenant')
    assign_action_trainer(e,a,t1,ADMIN,is_referent=True)
    assign_action_trainer(e,a,t2,ADMIN)
    for m in list_action_missions(e,a):
        if m['trainer_id']==t1:verify(e,m['mission_id'])
    assert not action_mission_coverage(e,a)['ready']
    assert not activate_action(e,a,ADMIN)[0]
    for m in list_action_missions(e,a):
        if m['trainer_id']==t2:verify(e,m['mission_id'])
    assert action_mission_coverage(e,a)['ready']


def test_subcontractor_supplier_must_have_real_active_link(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Sous-traitante test','SOUS_TRAITANT')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    mid=list_action_missions(e,a)[0]['mission_id']
    with pytest.raises(ValueError,match='fournisseur'):verify(e,mid)
    link_professional_supplier(e,p,'FOURNISSEUR-TEST-001',relationship_type='SOUS_TRAITANT',actor=ADMIN)
    with pytest.raises(ValueError,match='non lié'):verify(e,mid,supplier_id='FOURNISSEUR-TIERS')
    mission=verify(e,mid,supplier_id='FOURNISSEUR-TEST-001',cost_commitment_ref='COMMIT-17-001')
    assert mission['contract_kind']=='CONTRAT_SOUS_TRAITANCE'
    assert action_mission_coverage(e,a)['ready']
    evs=mission_outbox_pending(e,a)
    assert any(x.get('supplier_id')=='FOURNISSEUR-TEST-001' and x.get('cost_commitment_ref')=='COMMIT-17-001' for x in evs)
    assert all('amount_to_pay' not in x for x in evs)
    assert one(e,"SELECT COUNT(*) n FROM action_mission_outbox WHERE delivery_status='A_RACCORDER'")['n']==len(evs)


def test_unknown_collaboration_never_claimed_valid(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Statut à préciser','A_DEFINIR')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    with pytest.raises(ValueError,match='Statut de collaboration'):verify(e,list_action_missions(e,a)[0]['mission_id'])


def test_document_must_be_accepted_not_a_free_checkbox(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Justificatif incomplet')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    mid=list_action_missions(e,a)[0]['mission_id']
    for data in ({'document_ref':''},{'document_version':''},{'accepted_at':'invalide'}):
        with pytest.raises(ValueError):verify(e,mid,**data)
    assert not action_mission_coverage(e,a)['ready']


def test_verified_document_is_immutable_until_revision(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Révision avenant')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    mid=list_action_missions(e,a)[0]['mission_id']
    verify(e,mid)
    with pytest.raises(ValueError):verify(e,mid,document_ref='DOC-V2')
    new=revise_mission(e,mid,ADMIN,'Avenant de durée')
    assert new['revised_from']==mid and new['status']=='A_PREPARER'
    old=one(e,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':mid})
    assert old['document_ref']=='DOC-VALIDE-J8' and not old['active']
    assert not action_mission_coverage(e,a)['ready']
    verify(e,new['mission_id'],document_ref='DOC-V2',document_version='v2')
    assert action_mission_coverage(e,a)['ready']
    assert len(list_trainer_missions(e,t))==2


def test_unassign_keeps_document_history_and_blocks_followup(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Fin affectation')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    mid=list_action_missions(e,a)[0]['mission_id']
    verify(e,mid)
    assert unassign_action_trainer(e,a,t,ADMIN,'Changement équipe')[0]
    old=one(e,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':mid})
    assert old['status']=='REMPLACE' and old['document_ref']=='DOC-VALIDE-J8'
    assert not action_mission_coverage(e,a)['ready']
    assert any(x['event_type']=='MISSION_REPLACED' for x in mission_outbox_pending(e,a))


def test_no_cross_action_leakage_of_mission_information(env):
    e,c=env;a=new_action(e,c,'J8-A');b=new_action(e,c,'J8-B')
    p,t=person(e,'Personne multiaction')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    assign_action_trainer(e,b,t,ADMIN,is_referent=True)
    assert {x['action_id'] for x in list_trainer_missions(e,t)}=={a,b}
    assert all(x['action_id']==a for x in list_action_missions(e,a))
    assert all(x['gda_action_id']==a for x in mission_outbox_pending(e,a))


def test_mission_event_keys_idempotent_and_versioned(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Contrat stable')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    events=mission_outbox_pending(e,a)
    assert events and events[0]['format']=='CLARTE360_GDA_MISSION_EVENT_V1'
    assert events[0]['no_clar']=='J8-001'
    keys=[x['event_id'] for x in events]
    assert len(keys)==len(set(keys))
    assert not any('birth_date' in json.dumps(x) or 'beneficiary' in json.dumps(x) for x in events)


def test_check_no_unverified_financial_status(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Fournisseur externalisé','SOUS_TRAITANT')
    link_professional_supplier(e,p,'S-001','SOUS_TRAITANT',actor=ADMIN)
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    verify(e,list_action_missions(e,a)[0]['mission_id'],cost_commitment_ref='CMT-001')
    statuses={x['delivery_status'] for x in q(e,'SELECT delivery_status FROM action_mission_outbox')}
    assert statuses=={'A_RACCORDER'}
    assert 'paye' not in json.dumps(mission_outbox_pending(e,a)).lower()


def test_only_legacy_policy_is_preview_not_silent_backfill(env):
    e,c=env;a=new_action(e,c,new=False)
    init_db(e)
    assert one(e,'SELECT * FROM action_mission_policy WHERE action_id=:a',{'a':a}) is None
    enable_action_mission_control(e,a,ADMIN)
    assert not activate_action(e,a,ADMIN)[0]


def test_mission_assignments_rollback_on_bad_ref(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Contrôle fournisseur','SOUS_TRAITANT')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    mid=list_action_missions(e,a)[0]['mission_id']
    with pytest.raises(ValueError):verify(e,mid,supplier_id='INCONNU')
    m=one(e,'SELECT * FROM action_mission_engagements WHERE mission_id=:m',{'m':mid})
    assert m['document_ref'] is None and m['status']=='A_PREPARER'


def test_unknown_actor_cannot_certify_engagement(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Contrôle acteur')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    m=list_action_missions(e,a)[0]
    with pytest.raises(PermissionError):verify_mission_engagement(e,m['mission_id'],'inconnu@example.com',
        document_ref='DOC-ALIAS',document_version='v1',accepted_at=DOC_DATE)
    assert not action_mission_coverage(e,a)['ready']


def test_acceptance_timestamp_must_include_timezone(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Contrôle date')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    with pytest.raises(ValueError):verify(e,list_action_missions(e,a)[0]['mission_id'],accepted_at='2026-10-10T13:00:00')


def test_replacing_referent_forces_both_roles_to_be_reviewed(env):
    e,c=env;a=new_action(e,c);p1,t1=person(e,'Ancien référent');p2,t2=person(e,'Nouveau référent')
    assign_action_trainer(e,a,t1,ADMIN,is_referent=True)
    assign_action_trainer(e,a,t2,ADMIN)
    for row in list_action_missions(e,a):verify(e,row['mission_id'])
    assert action_mission_coverage(e,a)['ready']
    assign_action_trainer(e,a,t2,ADMIN,is_referent=True)
    assert not action_mission_coverage(e,a)['ready']
    for m in list_action_missions(e,a,active_only=True):
        assert m['status']=='A_PREPARER'
        assert m['revised_from']


def test_supplier_link_revoked_revokes_coverage(env):
    from services import unlink_professional_supplier
    e,c=env;a=new_action(e,c);p,t=person(e,'Sous traitante reliée','SOUS_TRAITANT')
    link_professional_supplier(e,p,'SUPP-VALID','SOUS_TRAITANT',actor=ADMIN)
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    verify(e,list_action_missions(e,a)[0]['mission_id'])
    assert action_mission_coverage(e,a)['ready']
    unlink_professional_supplier(e,p,'SUPP-VALID',ADMIN)
    assert not action_mission_coverage(e,a)['ready']


def test_slot_only_trainer_is_detected(env):
    from services import assign_slot_trainer
    e,c=env;a=new_action(e,c);p1,t1=person(e,'Titulaire action');p2,t2=person(e,'Remplacant créneau')
    assign_action_trainer(e,a,t1,ADMIN,is_referent=True)
    verify(e,list_action_missions(e,a)[0]['mission_id'])
    sl=one(e,'SELECT id FROM slots WHERE action_id=:a',{'a':a})['id']
    assert assign_slot_trainer(e,sl,t2,ADMIN,role='REMPLACANT')[0]
    assert any('créneau affecté sans mission' in x for x in action_mission_coverage(e,a)['issues'])
    assert not activate_action(e,a,ADMIN)[0]


def test_j1_purge_preflight_includes_mission_rows_and_changes_fingerprint(env):
    from purge_guard import preview_action_purge
    e,c=env;a=new_action(e,c);p,t=person(e,'Candidat purge')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    before=preview_action_purge(e,a)
    assert before['counts']['action_mission_policy']==1
    assert before['counts']['action_mission_engagements']==1
    assert before['counts']['action_mission_outbox']>=1
    assert before['counts']['action_mission_events']>=1
    mid=list_action_missions(e,a)[0]['mission_id']
    verify(e,mid)
    after=preview_action_purge(e,a)
    assert after['fingerprint']!=before['fingerprint']
    assert after['counts']['action_mission_events']>=2


def test_fk_cascade_action_removes_mission_and_outbox(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Liaison historique')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    execute(e,'DELETE FROM actions WHERE id=:a',{'a':a})
    for table in ('action_mission_policy','action_mission_engagements','action_mission_events','action_mission_outbox'):
        assert one(e,f'SELECT COUNT(*) n FROM {table}')['n']==0
    assert one(e,'SELECT id FROM trainers WHERE id=:t',{'t':t}) is not None


def test_refusal_remains_queued_and_blocks_activation(env):
    from mission_engagements import change_mission_status
    e,c=env;a=new_action(e,c);p,t=person(e,'Sous-traitance refus')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    mid=list_action_missions(e,a)[0]['mission_id']
    change_mission_status(e,mid,ADMIN,'DEMANDE','Contrat transmis pour accord')
    change_mission_status(e,mid,ADMIN,'REFUSE','Intervenant a refusé la mission')
    assert not action_mission_coverage(e,a)['ready']
    events=mission_outbox_pending(e,a)
    assert any(x['event_type']=='MISSION_REFUSE' for x in events)
    assert one(e,'SELECT status FROM action_mission_engagements WHERE mission_id=:m',{'m':mid})['status']=='REFUSE'


def test_verified_cancelled_preserves_previous_document(env):
    from mission_engagements import change_mission_status
    e,c=env;a=new_action(e,c);p,t=person(e,'Annulation')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    mid=list_action_missions(e,a)[0]['mission_id']
    verify(e,mid)
    with pytest.raises(ValueError):change_mission_status(e,mid,ADMIN,'REFUSE','Ne doit pas effacer la preuve')
    cancelled=change_mission_status(e,mid,ADMIN,'ANNULE','Action reportée et mission annulée')
    assert cancelled['status']=='ANNULE' and cancelled['document_ref']=='DOC-VALIDE-J8' and not cancelled['active']
    assert not action_mission_coverage(e,a)['ready']


def test_anonymous_user_cannot_change_mission_status(env):
    from mission_engagements import change_mission_status
    e,c=env;a=new_action(e,c);p,t=person(e,'Admin controle')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    mid=list_action_missions(e,a)[0]['mission_id']
    with pytest.raises(PermissionError):change_mission_status(e,mid,'faux@example.com','ANNULE','Pas autorisé')


def test_admin_cannot_downgrade_mandatory_coverage_silently(env):
    e,c=env;a=new_action(e,c)
    with pytest.raises(ValueError):enable_action_mission_control(e,a,ADMIN,'PREVIEW')
    with pytest.raises(PermissionError):enable_action_mission_control(e,a,'autre@example.org','ENFORCE')


def test_archived_action_refuses_post_factum_engagement_verification(env):
    e,c=env;a=new_action(e,c);p,t=person(e,'Archivage document')
    assign_action_trainer(e,a,t,ADMIN,is_referent=True)
    mid=list_action_missions(e,a)[0]['mission_id']
    execute(e,"UPDATE actions SET status='ARCHIVEE' WHERE id=:a",{'a':a})
    with pytest.raises(ValueError,match='archivée'):verify(e,mid)
