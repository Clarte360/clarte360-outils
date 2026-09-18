import json
from pathlib import Path
from sqlalchemy import create_engine
from db import init_db
from services import upsert_tool_catalog, set_action_tool_allowed, action_allowed_tools, execute, utcnow_iso

def eng():
    e=create_engine('sqlite:///:memory:',future=True); init_db(e); return e

def test_non_pip_is_direct_and_pip_signed_and_version_preserved():
    e=eng()
    a=upsert_tool_catalog(e,{'tool_code':'DEMO','name':'Demo','base_url':'https://example.org','tool_version':'9.9','launch_type':'EXTERNAL_SIGNED'})
    assert a['launch_type']=='HUB_REDIRECT'
    b=upsert_tool_catalog(e,{'tool_code':'DEMO','name':'Demo','base_url':'https://example.org','active':True,'prescription_allowed':True})
    assert b['tool_version']=='9.9'
    p=upsert_tool_catalog(e,{'tool_code':'PIP_RIASEC_ONET','name':'PIP','base_url':'https://pip.example.org','launch_type':'HUB_REDIRECT'})
    assert p['launch_type']=='EXTERNAL_SIGNED'

def test_deactivating_tool_removes_action_authorization():
    e=eng(); n=utcnow_iso()
    oid=execute(e,"INSERT INTO organizations(name,legal_name,active,created_at,updated_at) VALUES('O','O',1,:n,:n)",{'n':n})
    aid=execute(e,"INSERT INTO actions(action_no,title,nature,prestation_type,mode,status,planned_hours,expected_participants,organization_id,created_at,updated_at) VALUES('A1','A','Formation','FORMATION','INDIVIDUEL','ACTIVE',1,1,:o,:n,:n)",{'o':oid,'n':n})
    upsert_tool_catalog(e,{'tool_code':'DEMO','name':'Demo','base_url':'https://example.org','active':True,'prescription_allowed':True})
    set_action_tool_allowed(e,aid,'DEMO',True)
    assert [x['tool_code'] for x in action_allowed_tools(e,aid)]==['DEMO']
    upsert_tool_catalog(e,{'tool_code':'DEMO','name':'Demo','base_url':'https://example.org','active':False,'prescription_allowed':False})
    assert action_allowed_tools(e,aid)==[]

def test_registry_has_no_business_compatibility_restrictions_and_direct_non_pip():
    data=json.loads((Path(__file__).parents[1]/'config/tool_registry.json').read_text())
    for tool in data['tools']:
        assert tool.get('compatible_prestations')==[]
        if tool['tool_code']=='PIP_RIASEC_ONET': assert tool['launch_type']=='EXTERNAL_SIGNED'
        else: assert tool['launch_type']=='HUB_REDIRECT'
