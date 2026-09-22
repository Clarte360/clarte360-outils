import json
from pathlib import Path

from db import make_engine, init_db, one, execute
from services import (
    seed_tool_catalog, upsert_tool_catalog, list_tool_catalog,
    create_action, add_participant, create_beneficiary, link_participant_to_beneficiary,
    set_action_tool_allowed, action_allowed_tools, create_tool_prescription,
    consume_pip_outbox,
)


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); seed_tool_catalog(e); return e


def seed_action(e):
    aid=create_action(e,{
        'action_no':'RC5-OUTILS','title':'Test outils','subtitle':None,'nature':'FORMATION','mode':'INDIVIDUEL',
        'client_name':'Client','client_type':'Entreprise','group_code':None,'planned_hours':2,
        'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Online','notes':None,'source':'TEST'
    },'test')
    pid,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'anne@example.org'},'test')
    bid=create_beneficiary(e,'DUPONT','Anne','1990-01-01','anne@example.org',actor='test')
    link_participant_to_beneficiary(e,pid,bid,'test')
    return aid,pid,bid


def test_roue_valeurs_is_deployed_active_and_prescriptible():
    e=eng(); r=one(e,"SELECT * FROM tool_catalog WHERE tool_code='ROUE_VALEURS'")
    assert r['active']==1 and r['prescription_allowed']==1
    assert r['base_url']=='https://roue-valeurs.clarte360.com'


def test_registry_is_source_of_truth_for_global_deployment_state():
    e=eng()
    roue=one(e,"SELECT active,prescription_allowed FROM tool_catalog WHERE tool_code='ROUE_VALEURS'")
    moteurs=one(e,"SELECT active,prescription_allowed FROM tool_catalog WHERE tool_code='MOTEURS_PROFESSIONNELS'")
    assert roue['active']==1 and roue['prescription_allowed']==1
    assert moteurs['active']==1 and moteurs['prescription_allowed']==1


def test_action_can_add_and_remove_tools_freely():
    e=eng(); aid,_,_=seed_action(e)
    assert set_action_tool_allowed(e,aid,'BOUSSOLE_VALEURS',True,'admin')[0]
    assert set_action_tool_allowed(e,aid,'ROUE_VALEURS',True,'admin')[0]
    assert {x['tool_code'] for x in action_allowed_tools(e,aid)}=={'BOUSSOLE_VALEURS','ROUE_VALEURS'}
    assert set_action_tool_allowed(e,aid,'BOUSSOLE_VALEURS',False,'admin')[0]
    assert {x['tool_code'] for x in action_allowed_tools(e,aid)}=={'ROUE_VALEURS'}


def test_beneficiary_portal_uses_direct_autonomous_links_and_fresh_pip_signed_link():
    src=Path('app.py').read_text(encoding='utf-8')
    block=src[src.index("with tabs[4]:"):src.index("with tabs[5]:")]
    assert "build_pip_prescription_launch" in block
    assert "launch_url=(pr.get('base_url')" in block
    assert "create_prescription_launch_token" not in block
    assert "vous pouvez le rouvrir à tout moment" in block


def test_pip_result_summary_is_persisted_from_outbox(tmp_path):
    e=eng(); aid,pid,bid=seed_action(e)
    set_action_tool_allowed(e,aid,'PIP_RIASEC_ONET',True,'admin')
    pr=create_tool_prescription(e,'PIP_RIASEC_ONET',bid,aid,pid,actor='admin')
    event={
        'event_type':'TERMINE','timestamp':'2026-09-17T18:00:00+00:00',
        'payload':{
            'beneficiary_id':str(bid),'action_id':str(aid),'participant_id':str(pid),
            'prescription_id':pr['prescription_id'],'passation_id':'PIP-XYZ','app_version':'1.0.8-l1-vps',
            'result_summary':{'journey':'PIP_SEUL','pip':{'holland_code':'RIA','indices':{'R':88,'I':72,'A':65},'order':['R','I','A'],'exact_ties':[]}}
        }
    }
    out=tmp_path/'outbox.jsonl'; out.write_text(json.dumps(event,ensure_ascii=False)+'\n',encoding='utf-8')
    r=consume_pip_outbox(e,str(out),'500' if False else 500,'test')
    assert r['processed']==1 and r['errors']==0
    row=one(e,'SELECT metadata_json FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']})
    meta=json.loads(row['metadata_json'])
    assert meta['pip_result_summary']['pip']['holland_code']=='RIA'
