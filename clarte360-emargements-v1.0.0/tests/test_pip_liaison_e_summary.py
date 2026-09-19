import json
import pytest
from db import make_engine, init_db, one, execute
from services import normalize_pip_result_summary, seed_tool_catalog, create_action, add_participant, create_beneficiary, link_participant_to_beneficiary, create_tool_prescription, consume_pip_outbox


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); seed_tool_catalog(e); return e


def seed(e):
    aid=create_action(e,{'action_no':'E-001','title':'Résumé PIP','nature':'BILAN_COMPETENCES','mode':'INDIVIDUEL','client_name':'Client','client_type':'Particulier','planned_hours':3,'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,'location':'Online','source':'TEST'},'test')
    pid,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'anne@example.org'},'test')
    bid=create_beneficiary(e,'DUPONT','Anne','1990-01-01','anne@example.org',actor='test'); link_participant_to_beneficiary(e,pid,bid,'test')
    pr=create_tool_prescription(e,'PIP_RIASEC_ONET',bid,aid,pid,actor='test'); return aid,pid,bid,pr


def test_e_canonical_summary_keeps_only_accompaniment_data():
    s=normalize_pip_result_summary({'method_versions':{'riasec':'2026.1'},'pip':{'scores':{'R':12,'I':34,'A':56,'S':78,'E':90,'C':11},'ranking':['E','S','A','I','R','C'],'holland_code':'ESA'},'onet':{'completed':True,'scores':{'Investigative':88},'ranking':['Investigative']},'feeling':'utile','report':{'reference':'secure:pdf:123'}},completed_at='2026-09-18T20:00:00Z',app_version='1.0.10')
    assert s['status']=='TERMINE' and s['pip']['holland_code']=='ESA' and len(s['pip']['scores'])==6
    assert s['onet']['completed'] is True and s['report']['reference']=='secure:pdf:123'
    assert s['method_versions']['pip_app']=='1.0.10'

@pytest.mark.parametrize('bad',[
 {'answers':[1,2,3]}, {'pip':{'pip_answers':[1]}}, {'onet':{'responses':[1]}}, {'email':'x@example.org'}, {'study_pseudonym':'abc'}
])
def test_e_rejects_raw_answers_identity_and_study_linkage(bad):
    with pytest.raises(ValueError): normalize_pip_result_summary(bad)


def test_e_termine_persists_canonical_summary_and_replay_is_idempotent(tmp_path):
    e=eng(); aid,pid,bid,pr=seed(e); path=tmp_path/'outbox.jsonl'
    ev={'event_type':'TERMINE','timestamp':'2026-09-18T20:00:00Z','payload':{'beneficiary_id':str(bid),'action_id':str(aid),'participant_id':str(pid),'prescription_id':pr['prescription_id'],'passation_id':'p1','app_version':'1.0.10','result_summary':{'pip':{'indices':{'R':10,'I':20,'A':30,'S':40,'E':50,'C':60},'order':['C','E','S','A','I','R'],'holland_code':'CES'},'onet':{'completed':False}}}}
    path.write_text(json.dumps(ev,separators=(',',':'))+'\n',encoding='utf-8')
    r=consume_pip_outbox(e,path); assert r['processed']==1 and r['errors']==0
    row=one(e,'SELECT metadata_json FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']}); s=json.loads(row['metadata_json'])['pip_result_summary']
    assert s['schema']=='clarte360.gestion-actions.pip-summary.v1' and s['pip']['ranking'][0]=='C'
    assert consume_pip_outbox(e,path)['processed']==0


def test_e_bad_raw_answers_event_is_rejected_without_cursor_advance(tmp_path):
    e=eng(); aid,pid,bid,pr=seed(e); path=tmp_path/'outbox.jsonl'
    ev={'event_type':'TERMINE','timestamp':'2026-09-18T20:00:00Z','payload':{'beneficiary_id':str(bid),'action_id':str(aid),'participant_id':str(pid),'prescription_id':pr['prescription_id'],'result_summary':{'pip':{'answers':[1,2]}}}}
    path.write_text(json.dumps(ev)+'\n',encoding='utf-8')
    r=consume_pip_outbox(e,path); assert r['errors']==1 and r['offset']==0
    row=one(e,'SELECT metadata_json FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']}); assert 'pip_result_summary' not in json.loads(row['metadata_json'] or '{}')
