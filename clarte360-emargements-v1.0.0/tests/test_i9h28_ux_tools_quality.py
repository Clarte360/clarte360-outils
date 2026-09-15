from db import make_engine, init_db, execute, one, q, utcnow_iso
from services import (
    upsert_tool_catalog, set_action_tool_allowed, action_allowed_tools,
    create_tool_prescription, cancel_tool_prescription_owned,
    create_beneficiary_report, beneficiary_reports, update_user_report,
    add_slot, set_generic_action_module, refresh_teams_occurrences
)


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e


def seed_action(e):
    now=utcnow_iso()
    oid=execute(e,"INSERT INTO organizations(name,legal_name,active,created_at,updated_at) VALUES('Org','Org',1,:n,:n)",{'n':now})
    aid=execute(e,"""INSERT INTO actions(action_no,title,nature,prestation_type,mode,status,planned_hours,expected_participants,organization_id,created_at,updated_at)
      VALUES('A1','Action','Bilan de compétences','BILAN_COMPETENCES','INDIVIDUEL','ACTIVE',2,1,:o,:n,:n)""",{'o':oid,'n':now})
    bid=execute(e,"INSERT INTO beneficiaries(public_id,first_name,last_name,birth_date,current_email,active,created_at,updated_at) VALUES('BEN-X','Jean','TEST','1990-01-01','j@test.fr',1,:n,:n)",{'n':now})
    pid=execute(e,"INSERT INTO participants(action_id,last_name,first_name,birth_date,email,active,beneficiary_id,created_at) VALUES(:a,'TEST','Jean','1990-01-01','j@test.fr',1,:b,:n)",{'a':aid,'b':bid,'n':now})
    return aid,pid,bid


def test_action_tool_allowlist_and_duplicate_guard_and_creator_cancel():
    e=eng(); aid,pid,bid=seed_action(e)
    upsert_tool_catalog(e,{'tool_code':'DEMO','name':'Demo','base_url':'https://example.org','launch_type':'HUB_REDIRECT','compatible_prestations':['BILAN_COMPETENCES']},'admin')
    ok,msg=set_action_tool_allowed(e,aid,'DEMO',True,'admin@example.org'); assert ok
    assert [x['tool_code'] for x in action_allowed_tools(e,aid)]==['DEMO']
    pr=create_tool_prescription(e,'DEMO',bid,aid,pid,prescriber_type='ADMIN',prescriber_id='admin@example.org',actor='admin@example.org')
    try:
        create_tool_prescription(e,'DEMO',bid,aid,pid,prescriber_type='TRAINER',prescriber_id='9',actor='trainer:9')
        assert False, 'duplicate should be rejected'
    except ValueError as ex:
        assert 'déjà prescrit' in str(ex)
    ok,msg=cancel_tool_prescription_owned(e,pr['prescription_id'],'TRAINER','9','trainer:9'); assert not ok
    ok,msg=cancel_tool_prescription_owned(e,pr['prescription_id'],'ADMIN','admin@example.org','admin@example.org'); assert ok
    assert one(e,'SELECT status FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']})['status']=='ANNULE'


def test_beneficiary_report_lifecycle_keeps_history():
    e=eng(); aid,pid,bid=seed_action(e)
    rid=create_beneficiary_report(e,aid,bid,'Incident','Sujet','Description',True)
    assert rid
    assert beneficiary_reports(e,action_id=aid)[0]['status']=='NOUVEAU'
    ok,msg=update_user_report(e,'BENEFICIARY',rid,'CLOTURE','Réponse faite','admin@example.org'); assert ok
    row=beneficiary_reports(e,action_id=aid)[0]
    assert row['status']=='CLOTURE' and row['admin_response']=='Réponse faite' and row['closed_at']
    assert one(e,"SELECT id FROM quality_issues WHERE action_id=:a AND source_role='BENEFICIAIRE'",{'a':aid})


def test_new_slot_is_immediately_mirrored_in_teams_occurrences_when_enabled():
    e=eng(); aid,pid,bid=seed_action(e)
    set_generic_action_module(e,aid,'TEAMS',True,'admin')
    sid=add_slot(e,aid,'2099-01-10','10:00','11:00','admin')
    occ=one(e,'SELECT * FROM teams_occurrences WHERE slot_id=:s',{'s':sid})
    assert occ and occ['action_id']==aid and occ['status']=='PLANNED'


def test_admin_action_tabs_are_isolated_in_source():
    src=open('app.py',encoding='utf-8').read()
    assert "('action_parametres', action_settings_tab)" in src
    assert "_run_ui_module(ctx,lambda fn=fn: fn(a),action_id=a['id'])" in src
    assert "Signature déjà enregistrée pour ce participant" in src
