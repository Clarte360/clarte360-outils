from db import make_engine, init_db, one, q, execute, utcnow_iso
from services import (
    create_action, add_participant, add_slot, create_beneficiary, link_participant_to_beneficiary,
    upsert_tool_catalog, set_action_tools_allowed, action_allowed_tools, create_tool_prescription,
    list_tool_prescriptions, action_purge_summary, purge_action, add_trainer, assign_trainer,
)
from security import hash_password


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e


def seed(e, no='RC2-001'):
    aid=create_action(e,{
        'action_no':no,'title':'Test RC2','subtitle':None,'nature':'Bilan de compétences','mode':'INDIVIDUEL',
        'client_name':'Client','client_type':'Particulier','group_code':None,'planned_hours':2,
        'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Distanciel','notes':None,'source':'TEST'
    },'admin')
    execute(e,"UPDATE actions SET prestation_type='BILAN_COMPETENCES',status='ACTIVE' WHERE id=:a",{'a':aid})
    pid,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'anne@example.org'},'admin')
    bid=create_beneficiary(e,'DUPONT','Anne','1990-01-01','anne@example.org',actor='admin')
    link_participant_to_beneficiary(e,pid,bid,'admin')
    return aid,pid,bid


def test_rc2_action_tool_selection_add_remove_persists_on_existing_database():
    e=eng(); aid,pid,bid=seed(e)
    for code,name in [('PIP_RIASEC_ONET','PIP'),('BOUSSOLE_VALEURS','Boussole')]:
        upsert_tool_catalog(e,{'tool_code':code,'name':name,'base_url':'https://example.org/'+code,
            'launch_type':'EXTERNAL_SIGNED','active':True,'prescription_allowed':True,
            'compatible_prestations':['BILAN_COMPETENCES']},'admin')

    # Simulate an existing production action with no permission rows at all.
    assert one(e,'SELECT COUNT(*) n FROM action_tool_permissions WHERE action_id=:a',{'a':aid})['n']==0
    saved=set_action_tools_allowed(e,aid,{'PIP_RIASEC_ONET','BOUSSOLE_VALEURS'},'admin')
    assert {x['tool_code'] for x in saved}=={'PIP_RIASEC_ONET','BOUSSOLE_VALEURS'}
    assert one(e,'SELECT COUNT(*) n FROM action_tool_permissions WHERE action_id=:a',{'a':aid})['n']==2

    # Remove one tool: history row remains but allowed becomes 0.
    saved=set_action_tools_allowed(e,aid,{'PIP_RIASEC_ONET'},'admin')
    assert {x['tool_code'] for x in saved}=={'PIP_RIASEC_ONET'}
    row=one(e,"SELECT allowed FROM action_tool_permissions WHERE action_id=:a AND tool_code='BOUSSOLE_VALEURS'",{'a':aid})
    assert row['allowed']==0
    assert one(e,"SELECT id FROM audit_log WHERE action_id=:a AND event_type='ACTION_TOOL_PERMISSIONS_REPLACED'",{'a':aid})


def test_rc2_duplicate_prescription_is_global_and_prescriber_display_is_explicit():
    e=eng(); aid,pid,bid=seed(e,'RC2-002')
    upsert_tool_catalog(e,{'tool_code':'BOUSSOLE_VALEURS','name':'Boussole','base_url':'https://example.org/b',
        'launch_type':'EXTERNAL_SIGNED','active':True,'prescription_allowed':True,
        'compatible_prestations':['BILAN_COMPETENCES']},'admin')
    set_action_tools_allowed(e,aid,{'BOUSSOLE_VALEURS'},'admin')
    execute(e,"INSERT INTO admins(email,password_hash,full_name,created_at) VALUES('admin@example.org',:p,'Dominique Admin',:n)",{'p':hash_password('MotDePasse123!'),'n':utcnow_iso()})
    pr=create_tool_prescription(e,'BOUSSOLE_VALEURS',bid,aid,pid,prescriber_type='ADMIN',prescriber_id='admin@example.org',prescriber_role='ADMINISTRATEUR',actor='admin@example.org')
    rows=list_tool_prescriptions(e,action_id=aid)
    assert rows[0]['prescriber_display']=='Dominique Admin — Administrateur'
    try:
        create_tool_prescription(e,'BOUSSOLE_VALEURS',bid,aid,pid,prescriber_type='TRAINER',prescriber_id='1',prescriber_role='INTERVENANT',actor='trainer')
        assert False, 'duplicate should be rejected before trainer permission matters'
    except ValueError as ex:
        assert 'déjà prescrit' in str(ex)


def test_rc2_purge_summary_detects_signatures_and_purge_removes_action_owned_data_preserving_people():
    e=eng(); aid,pid,bid=seed(e,'RC2-PURGE')
    sid=add_slot(e,aid,'2026-09-15','10:00','11:00','admin')
    execute(e,"INSERT INTO signatures(participant_id,slot_id,signed_at,signature_path,signature_sha256,signer_name,method,status) VALUES(:p,:s,:n,'','x','Anne','MANUSCRITE','VALIDE')",{'p':pid,'s':sid,'n':utcnow_iso()})
    tid=add_trainer(e,'Coach Test','coach@example.org','','admin'); assign_trainer(e,aid,tid,'admin')
    execute(e,"INSERT INTO trainer_countersignatures_v3(slot_id,trainer_id,trainer_name,trainer_email,signed_at,declaration_text,method,created_at) VALUES(:s,:t,'Coach Test','coach@example.org',:n,'ok','MANUSCRITE',:n)",{'s':sid,'t':tid,'n':utcnow_iso()})
    upsert_tool_catalog(e,{'tool_code':'PIP_RIASEC_ONET','name':'PIP','base_url':'https://example.org/p',
        'launch_type':'EXTERNAL_SIGNED','active':True,'prescription_allowed':True,
        'compatible_prestations':['BILAN_COMPETENCES']},'admin')
    set_action_tools_allowed(e,aid,{'PIP_RIASEC_ONET'},'admin')
    create_tool_prescription(e,'PIP_RIASEC_ONET',bid,aid,pid,prescriber_type='ADMIN',prescriber_id='admin@example.org',actor='admin')
    execute(e,"INSERT INTO quality_issues(action_id,issue_type,title,status,created_at) VALUES(:a,'TEST','Qualité','OUVERTE',:n)",{'a':aid,'n':utcnow_iso()})

    info=action_purge_summary(e,aid)
    assert info['signature_count']==2
    assert info['counts']['tool_prescriptions']==1
    assert info['counts']['action_tool_permissions']>=1

    ok,msg=purge_action(e,aid,'admin'); assert ok,msg
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':aid}) is None
    assert one(e,'SELECT id FROM tool_prescriptions WHERE action_id=:a',{'a':aid}) is None
    assert one(e,'SELECT id FROM action_tool_permissions WHERE action_id=:a',{'a':aid}) is None
    assert one(e,'SELECT id FROM quality_issues WHERE action_id=:a',{'a':aid}) is None
    # Permanent people remain available for other/future actions.
    assert one(e,'SELECT id FROM beneficiaries WHERE id=:b',{'b':bid}) is not None
    assert one(e,'SELECT id FROM trainers WHERE id=:t',{'t':tid}) is not None
