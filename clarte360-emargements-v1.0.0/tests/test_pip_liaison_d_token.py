import base64, json
from urllib.parse import urlparse, parse_qs
from db import make_engine, init_db, execute
from services import seed_tool_catalog, create_action, add_participant, create_beneficiary, link_participant_to_beneficiary, create_tool_prescription, build_pip_prescription_launch
from pip_connector import build_pip_launch_token

KEY='test-signing-key-for-pip-jalon-d-123456789'

def decode(token):
    part=token.split('.',1)[0]; part += '='*(-len(part)%4)
    return json.loads(base64.urlsafe_b64decode(part.encode()).decode())

def test_direct_builder_keeps_legacy_contract_when_display_context_absent():
    p=decode(build_pip_launch_token(beneficiary_id=1,action_id=2,prescription_id='PRX-X',participant_id=3,signing_key=KEY,rights=['PIP_RUN'],now_epoch=1000))
    assert p['beneficiary_id']=='1' and p['action_id']=='2' and p['participant_id']=='3'
    assert 'beneficiary_first_name' not in p and 'action_title' not in p

def test_prescription_launch_adds_signed_display_context_without_changing_rights():
    e=make_engine('sqlite:///:memory:'); init_db(e); seed_tool_catalog(e)
    aid=create_action(e,{'action_no':'BC-2026-0042','title':'Bilan de competences - Evolution','subtitle':None,'nature':'BILAN_COMPETENCES','mode':'INDIVIDUEL','client_name':'Client','client_type':'Particulier','group_code':None,'planned_hours':3,'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,'location':'Online','notes':None,'source':'TEST'},'test')
    execute(e,"UPDATE actions SET prestation_type='BILAN_COMPETENCES' WHERE id=:a",{'a':aid})
    pid,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'anne@example.org'},'test')
    bid=create_beneficiary(e,'DUPONT','Anne','1990-01-01','anne@example.org',actor='test')
    link_participant_to_beneficiary(e,pid,bid,'test')
    pr=create_tool_prescription(e,'PIP_RIASEC_ONET',bid,aid,pid,actor='test')
    token=parse_qs(urlparse(build_pip_prescription_launch(e,pr['prescription_id'],KEY)).query)['launch'][0]
    p=decode(token)
    assert p['beneficiary_first_name']=='Anne'
    assert p['beneficiary_last_name']=='DUPONT'
    assert p['action_number']=='BC-2026-0042'
    assert p['action_title']=='Bilan de competences - Evolution'
    assert set(p['rights'])=={'PIP_RUN','PIP_RESUME','PIP_STATUS','PIP_RESULT_READ'}
    assert 'email' not in p and 'birth_date' not in p
