import base64
import hashlib
import hmac
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from db import make_engine, init_db, one, execute
from services import (
    seed_tool_catalog, create_action, add_participant, create_beneficiary, link_participant_to_beneficiary,
    create_tool_prescription, build_pip_prescription_launch, consume_pip_outbox,
)
from pip_connector import build_pip_launch_token, build_pip_launch_url, read_outbox_from_offset

KEY='test-signing-key-for-pip-rc5-123456789'

def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); seed_tool_catalog(e); return e

def seed(e):
    aid=create_action(e,{'action_no':'I9E-001','title':'PIP connector','subtitle':None,'nature':'BILAN_COMPETENCES','mode':'INDIVIDUEL','client_name':'Client','client_type':'Particulier','group_code':None,'planned_hours':3,'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,'location':'Online','notes':None,'source':'TEST'},'test')
    execute(e,"UPDATE actions SET prestation_type='BILAN_COMPETENCES' WHERE id=:a",{'a':aid})
    pid,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'anne@example.org'},'test')
    bid=create_beneficiary(e,'DUPONT','Anne','1990-01-01','anne@example.org',actor='test')
    link_participant_to_beneficiary(e,pid,bid,'test')
    pr=create_tool_prescription(e,'PIP_RIASEC_ONET',bid,aid,pid,actor='test')
    return aid,pid,bid,pr

def decode_ref_token(token):
    pp,sp=token.split('.',1)
    pad='='*(-len(pp)%4); payload=json.loads(base64.urlsafe_b64decode((pp+pad).encode()).decode())
    expected=hmac.new(KEY.encode(),pp.encode('ascii'),hashlib.sha256).digest()
    spad='='*(-len(sp)%4); supplied=base64.urlsafe_b64decode((sp+spad).encode())
    assert hmac.compare_digest(expected,supplied)
    return payload

def test_i9e_schema_has_generic_connector_cursor():
    e=eng(); assert one(e,"SELECT name FROM sqlite_master WHERE type='table' AND name='connector_cursors'")

def test_i9e_launch_token_matches_rc5_contract_and_has_no_pii():
    tok=build_pip_launch_token(beneficiary_id=12,action_id=34,participant_id=56,prescription_id='PRX-ABC',signing_key=KEY,rights=['PIP_RIASEC'],now_epoch=1700000000,valid_seconds=900)
    p=decode_ref_token(tok)
    assert p['beneficiary_id']=='12' and p['action_id']=='34' and p['participant_id']=='56' and p['prescription_id']=='PRX-ABC'
    assert p['iat']==1700000000 and p['exp']==1700000900 and p['v']==1
    assert 'email' not in p and 'name' not in p and 'birth_date' not in p

def test_i9e_launch_url_uses_exact_pip_entry_contract():
    url=build_pip_launch_url('https://pip-riasec.clarte360.com','abc.def')
    qs=parse_qs(urlparse(url).query)
    assert qs['mode']==['accompagnement'] and qs['launch']==['abc.def']

def test_i9e_prescription_launch_uses_hub_ids_and_is_verifiable():
    e=eng(); aid,pid,bid,pr=seed(e)
    url=build_pip_prescription_launch(e,pr['prescription_id'],KEY,valid_seconds=600)
    qs=parse_qs(urlparse(url).query); p=decode_ref_token(qs['launch'][0])
    assert p['beneficiary_id']==str(bid) and p['action_id']==str(aid) and p['participant_id']==str(pid)
    assert p['prescription_id']==pr['prescription_id']

def test_i9e_consumes_rc5_outbox_and_is_idempotent(tmp_path):
    e=eng(); aid,pid,bid,pr=seed(e); path=tmp_path/'gestion_actions_events.jsonl'
    events=[
      {'event_type':'CONSULTE','timestamp':'2026-09-12T10:00:00+00:00','payload':{'beneficiary_id':str(bid),'action_id':str(aid),'participant_id':str(pid),'prescription_id':pr['prescription_id'],'passation_id':'pass-1','app_version':'1.0.7-RC5'}},
      {'event_type':'EN_COURS','timestamp':'2026-09-12T10:01:00+00:00','payload':{'beneficiary_id':str(bid),'action_id':str(aid),'participant_id':str(pid),'prescription_id':pr['prescription_id'],'passation_id':'pass-1','app_version':'1.0.7-RC5'}},
      {'event_type':'TERMINE','timestamp':'2026-09-12T10:02:00+00:00','payload':{'beneficiary_id':str(bid),'action_id':str(aid),'participant_id':str(pid),'prescription_id':pr['prescription_id'],'passation_id':'pass-1','app_version':'1.0.7-RC5'}},
    ]
    path.write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in events),encoding='utf-8')
    r=consume_pip_outbox(e,path); assert r['processed']==3 and r['errors']==0
    row=one(e,'SELECT * FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']})
    assert row['status']=='TERMINE' and row['started_at'] and row['completed_at']
    refs=json.loads(row['result_refs_json']); assert refs[0]['passation_id']=='pass-1'
    r2=consume_pip_outbox(e,path); assert r2['processed']==0

def test_i9e_rejects_crossed_identity_without_advancing_bad_event(tmp_path):
    e=eng(); aid,pid,bid,pr=seed(e); path=tmp_path/'gestion_actions_events.jsonl'
    event={'event_type':'EN_COURS','timestamp':'2026-09-12T10:01:00+00:00','payload':{'beneficiary_id':'999999','action_id':str(aid),'participant_id':str(pid),'prescription_id':pr['prescription_id']}}
    path.write_text(json.dumps(event)+'\n',encoding='utf-8')
    r=consume_pip_outbox(e,path); assert r['errors']==1 and r['offset']==0
    assert one(e,'SELECT status FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']})['status']=='A_FAIRE'

def test_i9e_partial_jsonl_line_is_not_consumed(tmp_path):
    p=tmp_path/'outbox.jsonl'; p.write_bytes(b'{"event_type":"CONSULTE"')
    rows,offset=read_outbox_from_offset(p,0); assert rows==[] and offset==0

def test_i9e_app_hides_connector_failure_and_uses_signed_launch():
    text=Path('app.py').read_text(encoding='utf-8')
    block=text[text.index('def tool_launch_page'):text.index('# ROUTING PUBLIC SIGNATURE')]
    assert 'build_pip_prescription_launch' in block
    assert 'launch_signing_key' in block
    assert 'Meeting ID' not in block and 'Entra' not in block
    assert 'temporairement indisponible' in block

def test_i9e_worker_processes_pip_before_smtp_early_return():
    text=Path('worker.py').read_text(encoding='utf-8')
    pos_pip=text.index('consume_pip_outbox',text.index('def run_once'))
    pos_smtp=text.index("if not smtp.get('enabled')",text.index('def run_once'))
    assert pos_pip < pos_smtp

def test_i9e_runtime_connector_status_depends_on_config_without_storing_secret():
    from services import refresh_pip_connector_runtime_status
    e=eng()
    assert refresh_pip_connector_runtime_status(e,KEY,'/srv/pip/outbox.jsonl')=='CONNECTED'
    row=one(e,"SELECT connector_status,metadata_json FROM tool_catalog WHERE tool_code='PIP_RIASEC_ONET'")
    assert row['connector_status']=='CONNECTED' and KEY not in (row.get('metadata_json') or '')
