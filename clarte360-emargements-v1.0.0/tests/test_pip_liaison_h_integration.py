import base64
import hashlib
import hmac
import json
from pathlib import Path

from db import make_engine, init_db, execute, one, q
from services import (
    seed_tool_catalog, create_action, add_participant, create_beneficiary,
    link_participant_to_beneficiary, create_tool_prescription,
    build_pip_prescription_launch, process_pip_accompaniment_event,
    process_pip_public_event, process_signed_pip_event,
    archive_pip_report_pdf, get_pip_prescription_report,
)
from urllib.parse import urlparse, parse_qs

KEY='test-signing-key-for-pip-h-contract-123456789'


def decode(token):
    part=token.split('.',1)[0]
    part += '='*(-len(part)%4)
    return json.loads(base64.urlsafe_b64decode(part.encode()).decode())


def setup_prescription(tmp_path):
    e=make_engine('sqlite:///' + str(tmp_path/'h.db')); init_db(e); seed_tool_catalog(e)
    aid=create_action(e,{'action_no':'CLA0003','title':'Bilan de compétences','subtitle':None,'nature':'BILAN_COMPETENCES','mode':'INDIVIDUEL','client_name':'Client','client_type':'Particulier','group_code':None,'planned_hours':3,'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,'location':'Online','notes':None,'source':'TEST'},'test')
    execute(e,"UPDATE actions SET prestation_type='BILAN_COMPETENCES' WHERE id=:a",{'a':aid})
    pid,_=add_participant(e,aid,{'last_name':'MARTIN','first_name':'Alice','birth_date':'1990-01-01','email':'alice@example.org'},'test')
    bid=create_beneficiary(e,'MARTIN','Alice','1990-01-01','alice@example.org',actor='test')
    link_participant_to_beneficiary(e,pid,bid,'test')
    pr=create_tool_prescription(e,'PIP_RIASEC_ONET',bid,aid,pid,actor='test')
    return e, aid, pid, bid, pr


def test_launch_token_matches_pip_e1_common_hub_vocabulary(tmp_path):
    e,aid,pid,bid,pr=setup_prescription(tmp_path)
    token=parse_qs(urlparse(build_pip_prescription_launch(e,pr['prescription_id'],KEY)).query)['launch'][0]
    p=decode(token)
    expected={'PIP_RUN','PIP_RESUME','PIP_STATUS','PIP_RESULT_READ'}
    assert set(p['rights'])==expected
    assert set(p['scopes'])==expected
    assert p['tool_id']=='pip-riasec-onet'
    assert p['hub_source']=='GESTION_ACTIONS_I9_H1'
    assert p['return_mode']=='OUTBOX'
    assert p['beneficiary_first_name']=='Alice' and p['beneficiary_last_name']=='MARTIN'
    assert p['action_number']=='CLA0003' and p['action_title']=='Bilan de compétences'


def test_exact_pip_e1_termine_payload_is_consumed_without_raw_answers(tmp_path):
    e,aid,pid,bid,pr=setup_prescription(tmp_path)
    event={
        'event_type':'TERMINE','timestamp':'2026-09-18T20:30:00+00:00',
        'payload':{
            'beneficiary_id':str(bid),'action_id':str(aid),'participant_id':str(pid),
            'prescription_id':pr['prescription_id'],'passation_id':'PASS-E1','app_version':'1.0.10-l1-vps-hub-ready-guard-accompagnement',
            'result_summary':{
                'journey':'PIP_PUIS_ONET',
                'pip':{'holland_code':'RIA','indices':{'R':88,'I':72,'A':65,'S':40,'E':30,'C':25},'order':['R','I','A','S','E','C'],'exact_ties':[],'algorithm_version':'PIP-SCORE-1.0'},
                'onet':{'completed':True,'results':[{'name':'Investigative','score':28,'rank':1}]},
            }
        }
    }
    r=process_pip_accompaniment_event(e,event,raw_line=json.dumps(event,separators=(',',':')))
    assert not r['replayed']
    row=one(e,'SELECT status,metadata_json FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']})
    assert row['status']=='TERMINE'
    meta=json.loads(row['metadata_json'])['pip_result_summary']
    assert meta['pip']['holland_code']=='RIA'
    assert 'answers' not in json.dumps(meta).lower()


def test_public_verified_then_update_then_callback_are_idempotent_and_separated(tmp_path):
    e=make_engine('sqlite:///' + str(tmp_path/'public.db')); init_db(e)
    verified={'event_id':'pub-1','event_type':'CONTACT_EMAIL_VERIFIED','timestamp':'2026-09-18T20:31:00Z','payload':{
        'first_name':'Ada','last_name':'Lovelace','email':'Ada@Example.com','phone':'+33102030405','job_title':'Ingénieure','company':'Analytical','marketing_consent':False,'rgpd_notice_version':'RGPD-1','interests':['Coaching']}}
    process_pip_public_event(e,verified)
    process_pip_public_event(e,verified)
    c=one(e,'SELECT * FROM crm_contacts WHERE lower(email)=:e',{'e':'ada@example.com'})
    ints=json.loads(c['interests_json'])
    assert 'PIP-RIASEC' in ints and 'Coaching' in ints
    assert one(e,'SELECT COUNT(*) n FROM crm_contacts WHERE lower(email)=:e',{'e':'ada@example.com'})['n']==1
    updated={'event_id':'pub-2','event_type':'CONTACT_UPDATED','timestamp':'2026-09-18T20:32:00Z','payload':{'first_name':'Ada','last_name':'Lovelace','email':'ada@example.com','phone':'+33102030405','job_title':'Lead','company':'Analytical','marketing_consent':True,'interests':['Bilan de compétences']}}
    process_pip_public_event(e,updated)
    c=one(e,'SELECT * FROM crm_contacts WHERE id=:i',{'i':c['id']}); ints=json.loads(c['interests_json'])
    assert c['job_title']=='Lead' and c['marketing_consent']==1
    assert set(['PIP-RIASEC','Coaching','Bilan de compétences']).issubset(set(ints))
    cb={'event_id':'pub-3','event_type':'CALLBACK_REQUESTED','timestamp':'2026-09-18T20:33:00Z','payload':{'email':'ada@example.com','requested_at':'2026-09-18T20:33:00Z'}}
    process_pip_public_event(e,cb); process_pip_public_event(e,cb)
    assert one(e,'SELECT COUNT(*) n FROM crm_callback_notifications WHERE external_event_id=:e',{'e':'pub-3'})['n']==1
    assert 'study' not in json.dumps(dict(c)).lower()


def test_public_event_rejects_study_join_key(tmp_path):
    e=make_engine('sqlite:///' + str(tmp_path/'bad.db')); init_db(e)
    bad={'event_id':'bad-1','event_type':'CONTACT_EMAIL_VERIFIED','payload':{'first_name':'A','last_name':'B','email':'a@example.com','study_id':'pseudo-1'}}
    try:
        process_pip_public_event(e,bad)
    except ValueError as exc:
        assert 'interdite' in str(exc)
    else:
        raise AssertionError('study_id must be rejected')


def test_signed_event_contract_accepts_good_hmac_and_rejects_bad(tmp_path):
    e=make_engine('sqlite:///' + str(tmp_path/'signed.db')); init_db(e)
    body={'event_id':'sig-1','event_type':'CONTACT_EMAIL_VERIFIED','timestamp':'2026-09-18T20:34:00Z','payload':{'first_name':'Ada','last_name':'Lovelace','email':'ada@example.com','marketing_consent':False}}
    raw=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    sig=hmac.new(KEY.encode(),raw,hashlib.sha256).hexdigest()
    env=dict(body,signature='sha256='+sig)
    process_signed_pip_event(e,env,KEY)
    assert one(e,'SELECT id FROM crm_contacts WHERE email=:e',{'e':'ada@example.com'})
    env2=dict(body,event_id='sig-2',signature='sha256='+'0'*64)
    try:
        process_signed_pip_event(e,env2,KEY)
    except ValueError as exc:
        assert 'Signature HMAC' in str(exc)
    else:
        raise AssertionError('bad signature must be rejected')


def test_separate_pip_and_onet_reports_can_be_archived_once_each(tmp_path, monkeypatch):
    import services
    e,aid,pid,bid,pr=setup_prescription(tmp_path)
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'docs'); services.BENEFICIARY_DOC_DIR.mkdir()
    pip_pdf=b'%PDF-1.4\nPIP\n%%EOF'
    onet_pdf=b'%PDF-1.4\nONET\n%%EOF'
    archive_pip_report_pdf(e,pr['prescription_id'],pip_pdf,document_kind='PIP_REPORT',source_event_id='pdf-1')
    archive_pip_report_pdf(e,pr['prescription_id'],onet_pdf,document_kind='ONET_REPORT',source_event_id='pdf-2')
    assert get_pip_prescription_report(e,pr['prescription_id'],'PIP_REPORT')['document_kind']=='PIP_REPORT'
    assert get_pip_prescription_report(e,pr['prescription_id'],'ONET_REPORT')['document_kind']=='ONET_REPORT'
    assert one(e,'SELECT COUNT(*) n FROM prescription_documents WHERE prescription_id=:p',{'p':pr['prescription_id']})['n']==2
