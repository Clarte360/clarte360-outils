import json
from types import SimpleNamespace
from db import make_engine, init_db
from services import (
    create_professional_candidate, store_professional_document,
    build_global_professional_ai_payload, save_global_professional_ai_analysis,
    latest_global_professional_ai_run, review_professional_ai_suggestion,
    get_professional_360
)
from qualification_ai import GlobalDossierAIGateway, GLOBAL_PROMPT_VERSION

def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e

def result():
    return {
        'profile':{'title':'Consultant','summary':'Experience documentee','specialties':['QSE']},
        'experiences':[{'role_title':'Responsable QSE','organization':'ACME','description':'Pilotage','start_date':None,'end_date':None,'source_document_id':None}],
        'education':[],'certifications':[],'languages':[],
        'identity_alerts':['Le certificat porte un autre nom.'],
        'missing_points':['Verifier identite du certificat.'],
        'service_candidates':[{
            'service_id':1,'service_level':2,'confidence':.7,'rationale':'Experience proche',
            'source_document_ids':[],'missing_points':['Verifier pratique'],
            'evidence':[],'criteria':[]
        }]
    }

def facts():
    r=result().copy()
    r.pop('service_candidates')
    return r

class FakeResponses:
    def __init__(self, with_image=False):
        self.with_image=with_image
        self.calls=0
    def create(self,**kwargs):
        self.calls+=1
        assert kwargs['store'] is False
        assert kwargs['text']['format']['type']=='json_schema'
        schema=kwargs['text']['format']['name']
        if schema=='dossier_professionnel_faits':
            if self.with_image:
                content=kwargs['input'][0]['content']
                assert any(x.get('type')=='input_image' for x in content)
            return SimpleNamespace(status='completed',output_text=json.dumps(facts()),usage=None)
        payload=json.loads(kwargs['input'][0]['content'][0]['text'])
        candidates=[]
        for service in payload['service_catalog']:
            candidates.append({
                'service_id':service['service_id'],'service_level':2,'confidence':.7,
                'rationale':'Experience proche','source_document_ids':[],
                'missing_points':['Verifier pratique'],'evidence':[],
                'criteria':[{
                    'criterion_id':c['criterion_id'],'proposed_level':0,'confidence':.5,
                    'rationale':'A confirmer','evidence_indexes':[]
                } for c in service.get('criteria',[])]
            })
        return SimpleNamespace(status='completed',output_text=json.dumps({'service_candidates':candidates}),usage=None)

def test_global_gateway_structured_and_human_first():
    fake=FakeResponses()
    g=GlobalDossierAIGateway('', 'gpt-test', client=SimpleNamespace(responses=fake))
    out=g.analyze({
        'person':{'declared_name':'Dominique Laurent'},
        'documents':[],
        'service_catalog':[{'service_id':1,'name':'Test','family':'Tests','criteria':[]}]
    })
    assert out['prompt_version']==GLOBAL_PROMPT_VERSION
    assert out['result']['identity_alerts']
    assert out['result']['service_candidates'][0]['service_id']==1
    assert fake.calls==2

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

def test_global_analysis_materializes_qualification_without_second_ai_call():
    from services import get_person_service_qualification, list_ai_analysis_runs
    e=eng(); p=create_professional_candidate(e,'Dominique Laurent',actor='admin@test')
    rid=save_global_professional_ai_analysis(e,p,result(),'admin@test','openai','gpt-test',GLOBAL_PROMPT_VERSION,'hash')
    detail=get_person_service_qualification(e,p,1)
    qual=detail.get('qualification') or {}
    assert qual.get('ai_value')==2
    assert round(float(qual.get('ai_confidence') or 0),1)==0.7
    runs=list_ai_analysis_runs(e,p,1)
    assert len(runs)==1
    assert json.loads(runs[0]['input_summary_json'])['source']=='GLOBAL_DOSSIER'

def test_global_gateway_accepts_image_content_in_same_user_analysis():
    fake=FakeResponses(with_image=True)
    g=GlobalDossierAIGateway('', 'gpt-test', client=SimpleNamespace(responses=fake))
    out=g.analyze({
        'person':{'declared_name':'Dominique Laurent'},
        'documents':[],
        'service_catalog':[{'service_id':1,'name':'Test','family':'Tests','criteria':[]}],
        'document_images':[{'document_id':4,'name':'diplome.jpg','category':'DIPLOME','data_url':'data:image/jpeg;base64,AA=='}]
    })
    assert out['result']['service_candidates'][0]['service_level']==2
