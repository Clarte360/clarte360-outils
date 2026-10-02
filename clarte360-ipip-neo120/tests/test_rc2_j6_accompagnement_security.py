import hashlib
import json
from pathlib import Path
import pytest

from clarte360_ipip.completion import mark_completed
from clarte360_ipip.connectors.gestion_actions import (
    GestionActionsPort,
    LaunchTokenError,
    bind_prescription,
    build_launch_token,
    prescription_status,
    report_document_ref,
    require_scope,
    verify_launch_token,
)

KEY='test-only-signing-key-abcdefghijklmnopqrstuvwxyz'

def payload(**kw):
    d={
        'v':2,'iat':1800000000,'exp':1800003600,
        'tool_id':'ipip-neo120','hub_source':'GESTION_ACTIONS_I9_H1',
        'beneficiary_id':'BEN-1','action_id':'ACT-1','participant_id':'PART-1','prescription_id':'PRESC-1',
        'scopes':['IPIP_RUN','IPIP_RESUME','IPIP_STATUS','IPIP_RESULT_READ']
    }
    d.update(kw); return d

def ctx(**kw):
    return verify_launch_token(build_launch_token(payload(**kw),KEY),KEY,now_epoch=1800000100)

def test_legacy_rights_alias_is_rejected():
    p=payload(); p.pop('scopes'); p['rights']=['IPIP_RUN','IPIP_RESUME','IPIP_STATUS','IPIP_RESULT_READ']
    with pytest.raises(LaunchTokenError):
        verify_launch_token(build_launch_token(p,KEY),KEY,now_epoch=1800000100)

def test_scope_guard_is_explicit():
    c=ctx(scopes=['IPIP_RUN'])
    require_scope(c,'IPIP_RUN')
    for scope in ('IPIP_RESUME','IPIP_STATUS','IPIP_RESULT_READ'):
        with pytest.raises(LaunchTokenError): require_scope(c,scope)

def test_prescription_status_rejects_crossed_identity(tmp_path):
    original=ctx(); bind_prescription(tmp_path,original,'RUN-1')
    with pytest.raises(LaunchTokenError): prescription_status(tmp_path,ctx(beneficiary_id='BEN-X'))
    with pytest.raises(LaunchTokenError): prescription_status(tmp_path,ctx(action_id='ACT-X'))
    with pytest.raises(LaunchTokenError): prescription_status(tmp_path,ctx(participant_id='PART-X'))

def test_completed_prescription_remains_bound_and_new_prescription_gets_new_run(tmp_path):
    c=ctx(); assert bind_prescription(tmp_path,c,'RUN-1')=='RUN-1'
    report=tmp_path/'reports'/'r.pdf'; report.parent.mkdir(); report.write_bytes(b'%PDF-safe')
    sha=hashlib.sha256(report.read_bytes()).hexdigest()
    mark_completed(tmp_path,'RUN-1',report_path=str(report),report_sha256=sha,report_version='0.8.0-RC2')
    assert prescription_status(tmp_path,c)=='TERMINE'
    assert bind_prescription(tmp_path,c,'RUN-NEW')=='RUN-1'
    c2=ctx(prescription_id='PRESC-2')
    assert bind_prescription(tmp_path,c2,'RUN-2')=='RUN-2'

def test_report_reference_is_minimal_complete_and_confined(tmp_path):
    c=ctx(); bind_prescription(tmp_path,c,'RUN-1')
    report=tmp_path/'reports'/'r.pdf'; report.parent.mkdir(); report.write_bytes(b'%PDF-safe')
    sha=hashlib.sha256(report.read_bytes()).hexdigest()
    mark_completed(tmp_path,'RUN-1',report_path=str(report),report_sha256=sha,report_version='0.8.0-RC2')
    ref=report_document_ref(tmp_path,'RUN-1',prescription_id=c.prescription_id)
    for key in ('report_id','prescription_id','passation_id','mime_type','size_bytes','sha256','version','created_at','storage_ref'):
        assert key in ref
    assert ref['prescription_id']=='PRESC-1' and ref['passation_id']=='RUN-1'
    assert ref['mime_type']=='application/pdf' and ref['version']=='0.8.0-RC2'
    assert not Path(ref['storage_ref']).is_absolute()

    outside=tmp_path.parent/'outside.pdf'; outside.write_bytes(b'%PDF-outside')
    sha2=hashlib.sha256(outside.read_bytes()).hexdigest()
    mark_completed(tmp_path,'RUN-2',report_path=str(outside),report_sha256=sha2)
    with pytest.raises(ValueError): report_document_ref(tmp_path,'RUN-2',prescription_id='PRESC-2')

def test_outbox_refuses_raw_answers_even_nested(tmp_path):
    ga=GestionActionsPort(KEY,tmp_path)
    base={'beneficiary_id':'BEN-1','action_id':'ACT-1','prescription_id':'PRESC-1','participant_id':'PART-1','passation_id':'RUN-1'}
    with pytest.raises(ValueError): ga.publish_event('EN_COURS',{**base,'answers':{'1':5}})
    with pytest.raises(ValueError): ga.publish_event('EN_COURS',{**base,'result':{'raw_responses':[1,2,3]}})

def test_termine_report_must_match_prescription_and_run(tmp_path):
    ga=GestionActionsPort(KEY,tmp_path)
    base={'beneficiary_id':'BEN-1','action_id':'ACT-1','prescription_id':'PRESC-1','participant_id':'PART-1','passation_id':'RUN-1','status':'TERMINE'}
    doc={'report_id':'RID','prescription_id':'PRESC-X','passation_id':'RUN-1','file_name':'r.pdf','mime_type':'application/pdf','sha256':'0'*64,'size_bytes':100,'version':'1','created_at':'2026-10-02T00:00:00+00:00','storage_ref':'reports/r.pdf'}
    with pytest.raises(ValueError): ga.publish_event('TERMINE',{**base,'documents':[doc]})

def test_app_enforces_resume_status_and_result_scopes():
    src=Path('app.py').read_text(encoding='utf-8')
    assert "status_before_bind=='EN_COURS'" in src and "require_scope(ctx,'IPIP_RESUME')" in src
    assert "status_before_bind=='TERMINE'" in src and "require_scope(ctx,'IPIP_RESULT_READ')" in src
    assert "require_scope(ctx,'IPIP_STATUS')" in src
    assert "require_scope(c,'IPIP_STATUS')" in src
    assert "require_scope(c,'IPIP_RESULT_READ')" in src
    assert "report_document_ref(PERSISTENT_DATA_DIR,st.session_state.run_id,prescription_id=c.prescription_id,display_file_name=report_name)" in src

def test_only_launch_token_is_read_from_query_string():
    src=Path('app.py').read_text(encoding='utf-8')
    assert "st.query_params.get('launch'" in src
    for forbidden in ('beneficiary_id','action_id','prescription_id','participant_id'):
        assert f"st.query_params.get('{forbidden}'" not in src
