from db import make_engine, init_db
from services import *

def setup(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'j16.db')); init_db(e)
    p=create_professional_intervenant(e,'Dominique TEST',actor='admin')
    s=next(x for x in list_services(e) if x['service_code']=='BILAN_COMPETENCES')
    return e,p,s

def test_j16_materializes_ai_without_human_validation(tmp_path):
    e,p,s=setup(tmp_path); cr=list_service_criteria(e,s['id'])[0]
    result={'service_level':3,'confidence':.8,'rationale':'proposition','evidence':[{'source':'CV','fact':'experience','supports_level':3,'document_id':None,'criterion_ids':[cr['id']],'identity_status':'COHERENT'}],'missing_points':[],'criteria':[{'criterion_id':cr['id'],'proposed_level':3,'confidence':.75,'rationale':'preuve','evidence_indexes':[0]}]}
    save_ai_qualification_proposal(e,p,s['id'],result,'admin','openai','test','j16','hash')
    d=get_person_service_qualification(e,p,s['id'])
    assert d['qualification']['human_value'] is None
    assert d['evidence']==[]
    assert list_ai_evidence_proposals(e,p,s['id'])[0]['status']=='PROPOSEE'
    assert list_ai_criterion_proposals(e,p,s['id'])[0]['status']=='PROPOSEE'

def test_j16_human_acceptance_materializes_evidence_and_criterion(tmp_path):
    e,p,s=setup(tmp_path); cr=list_service_criteria(e,s['id'])[0]
    result={'service_level':3,'confidence':.8,'rationale':'proposition','evidence':[{'source':'CV','fact':'experience','supports_level':3,'document_id':None,'criterion_ids':[cr['id']],'identity_status':'COHERENT'}],'missing_points':[],'criteria':[{'criterion_id':cr['id'],'proposed_level':3,'confidence':.75,'rationale':'preuve','evidence_indexes':[0]}]}
    save_ai_qualification_proposal(e,p,s['id'],result,'admin','openai','test','j16','hash')
    ep=list_ai_evidence_proposals(e,p,s['id'])[0]; cp=list_ai_criterion_proposals(e,p,s['id'])[0]
    decide_ai_evidence_proposal(e,ep['id'],True,'admin'); decide_ai_criterion_proposal(e,cp['id'],True,'admin')
    d=get_person_service_qualification(e,p,s['id'])
    assert len(d['evidence'])==1
    c=next(x for x in d['criteria'] if x['id']==cr['id']); assert c['assessment_value']==3

def test_j16_identity_mismatch_cannot_be_accepted(tmp_path):
    e,p,s=setup(tmp_path); cr=list_service_criteria(e,s['id'])[0]
    result={'service_level':1,'confidence':.3,'rationale':'doute','evidence':[{'source':'Attestation','fact':'nom different','supports_level':3,'document_id':None,'criterion_ids':[cr['id']],'identity_status':'INCOHERENT'}],'missing_points':['Verifier identite'],'criteria':[{'criterion_id':cr['id'],'proposed_level':0,'confidence':.2,'rationale':'identite incoherente','evidence_indexes':[0]}]}
    save_ai_qualification_proposal(e,p,s['id'],result,'admin','openai','test','j16','hash')
    ep=list_ai_evidence_proposals(e,p,s['id'])[0]
    try: decide_ai_evidence_proposal(e,ep['id'],True,'admin'); assert False
    except ValueError: pass
    assert get_person_service_qualification(e,p,s['id'])['evidence']==[]

def test_j16_identical_human_validation_is_idempotent(tmp_path):
    e,p,s=setup(tmp_path)
    set_human_service_qualification(e,p,s['id'],3,'admin','OK',True)
    set_human_service_qualification(e,p,s['id'],3,'admin','OK',True)
    d=get_person_service_qualification(e,p,s['id'])
    assert len([h for h in d['history'] if h['event_type']=='SERVICE_HUMAN_VALIDATION'])==1
