import json
from types import SimpleNamespace
from db import make_engine, init_db, q
from services import create_professional_candidate, store_professional_document, build_global_professional_ai_payload, save_global_professional_ai_analysis, latest_global_professional_ai_run, review_professional_ai_suggestion, get_professional_360
from qualification_ai import GlobalDossierAIGateway, GLOBAL_PROMPT_VERSION

def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e

def result():
    return {'profile':{'title':'Consultant','summary':'Experience documentee','specialties':['QSE']},'experiences':[{'role_title':'Responsable QSE','organization':'ACME','description':'Pilotage','start_date':None,'end_date':None,'source_document_id':None}],'education':[],'certifications':[],'languages':[],'identity_alerts':['Le certificat porte un autre nom.'],'missing_points':['Verifier identite du certificat.'],'service_candidates':[{'service_id':1,'confidence':.7,'rationale':'Experience proche','source_document_ids':[]}]}

def test_global_gateway_structured_and_human_first():
    class R:
        def create(self,**kwargs):
            assert kwargs['store'] is False; assert kwargs['text']['format']['type']=='json_schema'
            return SimpleNamespace(status='completed',output_text=json.dumps(result()),usage=None)
    g=GlobalDossierAIGateway('', 'gpt-test', client=SimpleNamespace(responses=R()))
    out=g.analyze({'person':{'declared_name':'Dominique Laurent'},'documents':[],'service_catalog':[]})
    assert out['prompt_version']==GLOBAL_PROMPT_VERSION and out['result']['identity_alerts']

def test_global_analysis_creates_proposals_not_silent_profile_changes():
    e=eng(); p=create_professional_candidate(e,'Dominique Laurent',actor='admin@test')
    payload=build_global_professional_ai_payload(e,p,[]); assert payload['person']['declared_name']=='Dominique Laurent'
    rid=save_global_professional_ai_analysis(e,p,result(),'admin@test','openai','gpt-test',GLOBAL_PROMPT_VERSION,'hash')
    prof=get_professional_360(e,p); assert prof.get('summary') in (None,'')
    run=latest_global_professional_ai_run(e,p); assert run['id']==rid
    alerts=[x for x in run['suggestions'] if x['suggestion_type']=='IDENTITY_ALERT']; assert alerts and alerts[0]['status']=='PROPOSE'
    profile=[x for x in run['suggestions'] if x['suggestion_type']=='PROFILE'][0]
    review_professional_ai_suggestion(e,profile['id'],'ACCEPTE','admin@test')
    assert get_professional_360(e,p)['summary']=='Experience documentee'

def test_documents_are_persistent_and_linked_to_dossier():
    e=eng(); p=create_professional_candidate(e,'Doc Test',actor='admin@test')
    did=store_professional_document(e,p,b'%PDF-1.4 test','cv.pdf','CV','admin@test')
    prof=get_professional_360(e,p); assert any(x['id']==did and x['display_name']=='cv.pdf' for x in prof['documents'])
