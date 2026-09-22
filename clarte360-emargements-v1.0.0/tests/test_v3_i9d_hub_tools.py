from pathlib import Path
import pytest

from db import make_engine, init_db, one, q, execute
from services import (
    create_action, add_participant, create_beneficiary, link_participant_to_beneficiary,
    add_trainer, assign_action_trainer, seed_tool_catalog, list_tool_catalog,
    upsert_tool_catalog, create_tool_prescription, list_tool_prescriptions,
    create_prescription_launch_token, resolve_prescription_launch_token,
    set_action_trainer_prescription_permission, trainer_can_prescribe_tools,
    update_tool_prescription_status, prescription_events,
)


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); seed_tool_catalog(e); return e


def seed_action(e,no='I9D-001',prestation='BILAN_COMPETENCES'):
    aid=create_action(e,{
        'action_no':no,'title':'Hub I9-D','subtitle':None,'nature':prestation,'mode':'INDIVIDUEL',
        'client_name':'Client','client_type':'Particulier','group_code':None,'planned_hours':3,
        'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Online','notes':None,'source':'TEST'
    },'test')
    execute(e,'UPDATE actions SET prestation_type=:p WHERE id=:a',{'p':prestation,'a':aid})
    pid,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'anne@example.org'},'test')
    bid=create_beneficiary(e,'DUPONT','Anne','1990-01-01','anne@example.org',actor='test')
    link_participant_to_beneficiary(e,pid,bid,'test')
    return aid,pid,bid


def test_i9d_additive_schema_contains_generic_catalog_prescriptions_tokens_events_and_permission():
    e=eng()
    tables={x['name'] for x in q(e,"SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ('tool_catalog','tool_prescriptions','prescription_access_tokens','prescription_events'):
        assert t in tables
    cols={x['name'] for x in q(e,'PRAGMA table_info(action_trainers)')}
    assert 'can_prescribe_tools' in cols


def test_i9d_seeded_pip_is_documented_but_connector_waits_for_i9e():
    e=eng(); row=one(e,"SELECT * FROM tool_catalog WHERE tool_code='PIP_RIASEC_ONET'")
    assert row['tool_version']=='1.0.10-ACCOMPAGNEMENT'
    assert row['base_url']=='https://pip-riasec.clarte360.com'
    assert row['launch_type']=='EXTERNAL_SIGNED'
    assert row['connector_status']=='CONNECTED'


def test_i9d_generic_catalog_accepts_another_tool_without_pip_specific_fields():
    e=eng()
    row=upsert_tool_catalog(e,{
        'tool_code':'DEMO_GENERIC','name':'Outil générique','category':'COACHING','base_url':'https://example.org/tool',
        'tool_version':'1.0','launch_type':'HUB_REDIRECT','allowed_publics':['BENEFICIAIRE'],
        'compatible_prestations':['BILAN_COMPETENCES'],'access_validity_hours':24,
    },'admin')
    assert row['tool_code']=='DEMO_GENERIC'
    tools=list_tool_catalog(e,prescription_only=True,prestation_type='BILAN_COMPETENCES')
    assert any(x['tool_code']=='DEMO_GENERIC' for x in tools)


def test_i9d_admin_can_prescribe_generic_tool_to_existing_beneficiary_and_action():
    e=eng(); aid,pid,bid=seed_action(e)
    upsert_tool_catalog(e,{'tool_code':'DEMO','name':'Demo','base_url':'https://example.org','launch_type':'HUB_REDIRECT','compatible_prestations':['BILAN_COMPETENCES']},'admin')
    pr=create_tool_prescription(e,'DEMO',bid,aid,pid,prescriber_type='ADMIN',prescriber_id='admin@example.org',prescriber_role='ADMINISTRATEUR',actor='admin@example.org')
    assert pr['prescription_id'].startswith('PRX-') and pr['status']=='A_FAIRE'
    rows=list_tool_prescriptions(e,beneficiary_id=bid)
    assert len(rows)==1 and rows[0]['tool_name']=='Demo' and rows[0]['action_no']=='I9D-001'


def test_i9d_launch_token_is_hashed_single_use_and_marks_consulted():
    e=eng(); aid,pid,bid=seed_action(e)
    upsert_tool_catalog(e,{'tool_code':'DEMO','name':'Demo','base_url':'https://example.org','launch_type':'HUB_REDIRECT','compatible_prestations':['BILAN_COMPETENCES']},'admin')
    pr=create_tool_prescription(e,'DEMO',bid,aid,pid,actor='admin')
    token=create_prescription_launch_token(e,pr['prescription_id'],'beneficiary:1',15)
    stored=one(e,'SELECT * FROM prescription_access_tokens WHERE prescription_id=:p',{'p':pr['prescription_id']})
    assert stored and token not in stored['token_hash'] and len(stored['token_hash'])==64
    ctx=resolve_prescription_launch_token(e,token,'beneficiary:1')
    assert ctx['base_url']=='https://example.org'
    assert one(e,'SELECT status FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']})['status']=='CONSULTE'
    assert resolve_prescription_launch_token(e,token,'beneficiary:1') is None


def test_i9d_prescription_status_events_are_traceable_and_idempotent_by_event_id():
    e=eng(); aid,pid,bid=seed_action(e)
    upsert_tool_catalog(e,{'tool_code':'DEMO','name':'Demo','base_url':'https://example.org','launch_type':'HUB_REDIRECT','compatible_prestations':['BILAN_COMPETENCES']},'admin')
    pr=create_tool_prescription(e,'DEMO',bid,aid,pid,actor='admin')
    update_tool_prescription_status(e,pr['prescription_id'],'EN_COURS','connector',event_id='evt-1')
    update_tool_prescription_status(e,pr['prescription_id'],'TERMINE','connector',event_id='evt-1')
    assert one(e,'SELECT status FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']})['status']=='EN_COURS'
    assert len([x for x in prescription_events(e,pr['prescription_id']) if x.get('event_id')=='evt-1'])==1


def test_i9d_trainer_prescription_requires_explicit_action_permission():
    e=eng(); aid,pid,bid=seed_action(e)
    tid=add_trainer(e,'Coach','coach@example.org','','admin')
    assign_action_trainer(e,aid,tid,'admin')
    assert not trainer_can_prescribe_tools(e,tid,aid)
    ok,msg=set_action_trainer_prescription_permission(e,aid,tid,True,'admin')
    assert ok and trainer_can_prescribe_tools(e,tid,aid)


def test_i9d_beneficiary_portal_has_business_tool_tab_and_no_connector_technical_ids():
    text=Path('app.py').read_text(encoding='utf-8')
    block=text[text.index('def beneficiary_portal_page'):text.index('def footer')]
    assert 'Mes outils Clarté360' in block
    assert 'OUVRIR CET OUTIL' in block
    assert 'launch_token_ref' not in block and 'connector_code' not in block


def test_v31_tool_compatibility_metadata_does_not_block_other_action_types():
    e=eng(); aid,pid,bid=seed_action(e,prestation='FORMATION')
    upsert_tool_catalog(e,{'tool_code':'COACH_ONLY','name':'Coach only','base_url':'https://example.org','launch_type':'HUB_REDIRECT','compatible_prestations':['COACHING']},'admin')
    assert any(x['tool_code']=='COACH_ONLY' for x in list_tool_catalog(e,prescription_only=True,prestation_type='FORMATION'))
    pr=create_tool_prescription(e,'COACH_ONLY',bid,aid,pid,actor='admin')
    assert pr['status']=='A_FAIRE'


def test_i9h22_registry_seeds_deployed_tools_with_current_status():
    e=eng()
    b=one(e,"SELECT * FROM tool_catalog WHERE tool_code='BOUSSOLE_VALEURS'")
    assert b and b['active']==1 and b['prescription_allowed']==1
    assert b['base_url']=='https://boussole-valeurs.clarte360.com'
    moteurs=one(e,"SELECT * FROM tool_catalog WHERE tool_code='MOTEURS_PROFESSIONNELS'")
    assert moteurs and moteurs['active']==1 and moteurs['prescription_allowed']==1
    assert moteurs['base_url']=='https://moteurs-professionnels.clarte360.com'
    assert moteurs['connector_status']=='LAUNCH_ONLY'


def test_i9h22_generic_signed_launch_matches_boussole_contract():
    import base64, hashlib, hmac, json
    from urllib.parse import urlsplit, parse_qs
    from services import build_generic_tool_launch
    e=eng(); aid,pid,bid=seed_action(e)
    pr=create_tool_prescription(e,'BOUSSOLE_VALEURS',bid,aid,pid,prescriber_type='ADMIN',prescriber_role='ADMINISTRATEUR',actor='admin')
    secret='0123456789abcdef0123456789abcdef'
    url=build_generic_tool_launch(e,pr['prescription_id'],secret,900)
    qs=parse_qs(urlsplit(url).query); token=qs['hub_token'][0]; p,s=token.split('.',1)
    pad=lambda x:x+'='*((4-len(x)%4)%4)
    raw=base64.urlsafe_b64decode(pad(p)); sig=base64.urlsafe_b64decode(pad(s))
    assert hmac.compare_digest(sig,hmac.new(secret.encode(),p.encode(),hashlib.sha256).digest())
    payload=json.loads(raw)
    assert payload['tool_id']=='boussole-valeurs' and payload['role']=='admin'
    assert 'BOUSSOLE_RUN' in payload['scopes'] and payload['prescription_id']==pr['prescription_id']
    assert payload['beneficiary']['email']=='anne@example.org'


def test_i9h22_generic_signed_launch_requires_hub_secret():
    from services import build_generic_tool_launch
    e=eng(); aid,pid,bid=seed_action(e)
    pr=create_tool_prescription(e,'BOUSSOLE_VALEURS',bid,aid,pid,actor='admin')
    with pytest.raises(ValueError):
        build_generic_tool_launch(e,pr['prescription_id'],'short',900)
