import hashlib, json
from pathlib import Path
import pytest

from clarte360_ipip.connectors.gestion_actions import (
    GestionActionsPort, LaunchTokenError, bind_prescription, build_launch_token,
    prescription_status, report_document_ref, verify_launch_token
)
from clarte360_ipip.questionnaire import load_questionnaire, save_progress, load_progress, save_scoring_result
from clarte360_ipip.scoring import score_questionnaire
from clarte360_ipip.interpretation import load_interpretation, interpret_scoring
from clarte360_ipip.feedback import save_feedback, load_feedback
from clarte360_ipip.reporting import generate_report
from clarte360_ipip.completion import mark_completed, is_completed
from clarte360_ipip.framework.validation import ValidationError

KEY='test-only-signing-key-abcdefghijklmnopqrstuvwxyz'

def payload(prescription_id='PRESC-G-1', beneficiary_id='BEN-G-1', participant_id='PART-G-1', action_id='CLA-G-1'):
    return {
        'v':2,'iat':1800000000,'exp':1800003600,'tool_id':'ipip-neo120','hub_source':'GESTION_ACTIONS_I9_H1',
        'beneficiary_id':beneficiary_id,'action_id':action_id,'participant_id':participant_id,
        'prescription_id':prescription_id,'beneficiary_first_name':'Alice','beneficiary_last_name':'Martin',
        'scopes':['IPIP_RUN','IPIP_RESUME','IPIP_STATUS','IPIP_RESULT_READ']
    }

def context(**kw):
    p=payload(**kw)
    return verify_launch_token(build_launch_token(p,KEY),KEY,now_epoch=1800000100)

def resources():
    root=Path(__file__).resolve().parents[1]/'resources'/'ipip'
    q=load_questionnaire(root/'REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json')
    i=load_interpretation(root/'REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json')
    return q,i

def test_full_prescription_lifecycle_restart_and_lock(tmp_path):
    q,iref=resources(); ctx=context(); ga=GestionActionsPort(KEY,tmp_path)
    run='RUN-G-1'
    assert bind_prescription(tmp_path,ctx,run)==run
    ga.publish_event('CONSULTE',{'beneficiary_id':ctx.beneficiary_id,'action_id':ctx.action_id,'prescription_id':ctx.prescription_id,'participant_id':ctx.participant_id,'passation_id':run})

    first={i:3 for i in range(1,41)}
    save_progress(tmp_path,run,reference_version=q.version,answers=first,current_block=4)
    ga.publish_event('EN_COURS',{'beneficiary_id':ctx.beneficiary_id,'action_id':ctx.action_id,'prescription_id':ctx.prescription_id,'participant_id':ctx.participant_id,'passation_id':run})

    # simulated process/browser restart: reconstruct context and reload from disk
    ctx2=context(); assert bind_prescription(tmp_path,ctx2,'RUN-SHOULD-NOT-BE-CREATED')==run
    saved=load_progress(tmp_path,run,expected_reference_version=q.version)
    assert saved['answers']==first and saved['current_block']==4 and prescription_status(tmp_path,ctx2)=='EN_COURS'

    answers={i:((i-1)%5)+1 for i in range(1,121)}
    save_progress(tmp_path,run,reference_version=q.version,answers=answers,current_block=11)
    scored=score_questionnaire(q,answers); save_scoring_result(tmp_path,run,scored.to_dict())
    interp=interpret_scoring(scored,iref)
    fb={'global':4,'dominants':4,'nuances':4,'useful':5,'over':'','under':'','dialogue':'oui','free':'À approfondir en séance.'}
    save_feedback(tmp_path,run,fb)
    report=tmp_path/'reports'/f'{run}_v1.pdf'
    sha=generate_report(report,interpretation=interp,feedback=fb,app_version='0.7.0-rc1',reference_version=q.version,interpretation_version=iref.version)
    assert report.read_bytes().startswith(b'%PDF') and sha==hashlib.sha256(report.read_bytes()).hexdigest()
    mark_completed(tmp_path,run,report_path=str(report),report_sha256=sha)
    doc=report_document_ref(tmp_path,run)
    ga.publish_event('TERMINE',{'beneficiary_id':ctx.beneficiary_id,'action_id':ctx.action_id,'prescription_id':ctx.prescription_id,'participant_id':ctx.participant_id,'passation_id':run,'status':'TERMINE','documents':[doc]})

    assert is_completed(tmp_path,run) and prescription_status(tmp_path,ctx2)=='TERMINE'
    assert bind_prescription(tmp_path,ctx2,'RUN-NEW')==run
    assert doc['mime_type']=='application/pdf' and doc['sha256']==sha and doc['size_bytes']>0
    assert load_feedback(tmp_path,run)['global']==4

    with pytest.raises(ValidationError): save_progress(tmp_path,run,reference_version=q.version,answers=answers,current_block=11)
    with pytest.raises(ValidationError): save_scoring_result(tmp_path,run,scored.to_dict())
    with pytest.raises(ValidationError): save_feedback(tmp_path,run,fb)

    # a genuinely new prescription can create a new run
    ctx_new=context(prescription_id='PRESC-G-2')
    assert bind_prescription(tmp_path,ctx_new,'RUN-G-2')=='RUN-G-2'

def test_outbox_replay_is_idempotent_after_restart(tmp_path):
    ga=GestionActionsPort(KEY,tmp_path)
    p={'beneficiary_id':'BEN-G-1','action_id':'CLA-G-1','prescription_id':'PRESC-G-1','participant_id':'PART-G-1','passation_id':'RUN-G-1'}
    pending=ga.publish_event('EN_COURS',p)
    assert ga.retry_pending(lambda e: (_ for _ in ()).throw(RuntimeError('Gestion indisponible')))['failed']==1
    ga2=GestionActionsPort(KEY,tmp_path)
    delivered=[]
    assert ga2.retry_pending(lambda e: delivered.append(e['event_id']))['delivered']==1
    assert len(delivered)==1 and not pending.exists()
    # replaying same business event returns delivered artifact and cannot create a duplicate
    same=ga2.publish_event('EN_COURS',p)
    assert 'delivered' in str(same) and len(list((tmp_path/'connector_outbox'/'gestion_actions'/'delivered').glob('*.json')))==1

def test_crossing_and_bad_tokens_are_rejected(tmp_path):
    ctx=context(); bind_prescription(tmp_path,ctx,'RUN-G-1')
    with pytest.raises(LaunchTokenError): bind_prescription(tmp_path,context(beneficiary_id='BEN-OTHER'),'RUN-X')
    bad=build_launch_token(payload(),KEY)[:-2]+'aa'
    with pytest.raises(LaunchTokenError): verify_launch_token(bad,KEY,now_epoch=1800000100)
    expired=payload(); expired['exp']=1799999999
    with pytest.raises(LaunchTokenError): verify_launch_token(build_launch_token(expired,KEY),KEY,now_epoch=1800000100)

def test_termine_event_contains_no_raw_answers(tmp_path):
    ga=GestionActionsPort(KEY,tmp_path)
    payload_event={'beneficiary_id':'BEN','action_id':'ACT','prescription_id':'PRESC','participant_id':'PART','passation_id':'RUN','status':'TERMINE','documents':[{'report_id':'R','file_name':'r.pdf','mime_type':'application/pdf','sha256':'0'*64,'size_bytes':123,'storage_ref':'reports/r.pdf'}]}
    path=ga.publish_event('TERMINE',payload_event)
    env=json.loads(path.read_text())
    text=json.dumps(env)
    assert 'answers' not in text and 'responses' not in text
