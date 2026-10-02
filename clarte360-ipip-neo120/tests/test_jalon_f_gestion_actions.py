import json
from pathlib import Path
import pytest
from clarte360_ipip.connectors.gestion_actions import *
KEY='test-only-signing-key-abcdefghijklmnopqrstuvwxyz'
def payload(**kw):
 d={'v':2,'iat':1800000000,'exp':1800003600,'tool_id':'ipip-neo120','hub_source':'GESTION_ACTIONS_I9_H1','beneficiary_id':'BEN-1','action_id':'CLA0003','participant_id':'PART-1','prescription_id':'PRESC-1','beneficiary_first_name':'Alice','beneficiary_last_name':'Martin','scopes':['IPIP_RUN','IPIP_RESUME','IPIP_STATUS','IPIP_RESULT_READ']}; d.update(kw); return d
def test_token_hmac_and_scope():
 t=build_launch_token(payload(),KEY); c=verify_launch_token(t,KEY,now_epoch=1800000100); assert c.prescription_id=='PRESC-1'
 with pytest.raises(LaunchTokenError): verify_launch_token(build_launch_token(payload(tool_id='pip-riasec-onet'),KEY),KEY,now_epoch=1800000100)
 with pytest.raises(LaunchTokenError): verify_launch_token(build_launch_token(payload(scopes=['IPIP_STATUS']),KEY),KEY,now_epoch=1800000100)
def test_prescription_resume_and_anti_crossing(tmp_path):
 c=verify_launch_token(build_launch_token(payload(),KEY),KEY,now_epoch=1800000100); assert bind_prescription(tmp_path,c,'RUN-1')=='RUN-1'; assert bind_prescription(tmp_path,c,'RUN-2')=='RUN-1'; assert prescription_status(tmp_path,c)=='EN_COURS'
 bad=verify_launch_token(build_launch_token(payload(beneficiary_id='BEN-2'),KEY),KEY,now_epoch=1800000100)
 with pytest.raises(LaunchTokenError): bind_prescription(tmp_path,bad,'RUN-X')
def test_termine_locked_by_same_prescription(tmp_path):
 c=verify_launch_token(build_launch_token(payload(),KEY),KEY,now_epoch=1800000100); bind_prescription(tmp_path,c,'RUN-1'); (tmp_path/'completed').mkdir(); (tmp_path/'completed'/'RUN-1.json').write_text('{}'); assert prescription_status(tmp_path,c)=='TERMINE'; assert bind_prescription(tmp_path,c,'RUN-NEW')=='RUN-1'
def test_outbox_idempotent_and_hmac(tmp_path):
 p=GestionActionsPort(KEY,tmp_path); data={'beneficiary_id':'BEN-1','action_id':'CLA0003','prescription_id':'PRESC-1','participant_id':'PART-1','passation_id':'RUN-1'}; a=p.publish_event('EN_COURS',data); b=p.publish_event('EN_COURS',data); assert a==b; env=json.loads(a.read_text()); assert p.signed_delivery_headers(env)['X-Clarte360-Signature'].startswith('sha256=')
def test_retry_does_not_lose_failed_event(tmp_path):
 p=GestionActionsPort(KEY,tmp_path); path=p.publish_event('CONSULTE',{'beneficiary_id':'BEN-1','action_id':'CLA0003','prescription_id':'PRESC-1','passation_id':'RUN-1'}); r=p.retry_pending(lambda e: (_ for _ in ()).throw(RuntimeError('offline'))); assert r['failed']==1 and path.exists()
def test_report_ref_checks_sha(tmp_path):
 from clarte360_ipip.completion import mark_completed
 rp=tmp_path/'reports'/'r.pdf'; rp.parent.mkdir(); rp.write_bytes(b'%PDF-test'); import hashlib
 mark_completed(tmp_path,'RUN-1',report_path=str(rp),report_sha256=hashlib.sha256(b'%PDF-test').hexdigest()); ref=report_document_ref(tmp_path,'RUN-1'); assert ref['mime_type']=='application/pdf' and ref['size_bytes']==9 and len(ref['sha256'])==64
def test_no_raw_answers_in_connector_source():
 src=Path('clarte360_ipip/connectors/gestion_actions.py').read_text(); assert '_contains_forbidden_raw_data' in src and 'LAUNCH_SIGNING_KEY = "<secret' not in src
def test_app_requires_signed_launch_and_publishes_lifecycle():
    src=Path('app.py').read_text(encoding='utf-8')
    assert "st.query_params.get('launch'" in src
    assert "ga.resolve_launch(launch_token)" in src
    assert "bind_prescription(PERSISTENT_DATA_DIR" in src
    assert "publish_event('CONSULTE'" in src
    assert "publish_event('EN_COURS'" in src
    assert "publish_event('TERMINE'" in src
    assert src.index('generate_report(') < src.index("publish_event('TERMINE'")
    assert "'documents':[doc]" in src
