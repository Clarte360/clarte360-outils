import json
from types import SimpleNamespace

from db import make_engine, init_db, one
from services import (
    create_professional_candidate, list_services, list_service_criteria,
    add_qualification_evidence, update_qualification_evidence, delete_qualification_evidence,
    get_person_service_qualification
)
from qualification_ai import GlobalDossierAIGateway


def eng(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'rc21.db'))
    init_db(e)
    return e


def _facts():
    return {
        'profile':{'title':'Consultant','summary':'Dossier factuel','specialties':['QHSE']},
        'experiences':[],
        'education':[],
        'certifications':[],
        'languages':[],
        'identity_alerts':[],
        'missing_points':[]
    }


class FakeResponses:
    def __init__(self):
        self.calls=[]

    def create(self, **kwargs):
        self.calls.append(kwargs)
        schema=kwargs['text']['format']['name']
        if schema=='dossier_professionnel_faits':
            return SimpleNamespace(status='completed',output_text=json.dumps(_facts()),usage=None)
        payload=json.loads(kwargs['input'][0]['content'][0]['text'])
        out=[]
        for service in payload['service_catalog']:
            criteria=[{
                'criterion_id':c['criterion_id'],
                'proposed_level':0,
                'confidence':0.95,
                'rationale':'Aucun élément factuel ne démontre ce critère.',
                'evidence_indexes':[]
            } for c in service.get('criteria',[])]
            out.append({
                'service_id':service['service_id'],
                'service_level':0,
                'confidence':0.95,
                'rationale':'Aucun élément du dossier ne démontre actuellement cette prestation.',
                'source_document_ids':[],
                'missing_points':[],
                'evidence':[],
                'criteria':criteria
            })
        return SimpleNamespace(status='completed',output_text=json.dumps({'service_candidates':out}),usage=None)


def test_global_gateway_returns_every_active_service_in_batches(tmp_path):
    e=eng(tmp_path)
    services=list_services(e,active_only=True)
    assert services
    catalog=[]
    for s in services:
        catalog.append({
            'service_id':s['id'],
            'name':s['name'],
            'family':s.get('family') or '',
            'criteria':[{'criterion_id':c['id'],'label':c['label'],'required':bool(c['required']),'minimum_level':c['minimum_level']} for c in list_service_criteria(e,s['id'],active_only=True)]
        })
    fake=FakeResponses()
    g=GlobalDossierAIGateway('', 'gpt-test', client=SimpleNamespace(responses=fake))
    out=g.analyze({'person':{'declared_name':'Test'},'documents':[],'document_contents':[],'service_catalog':catalog})
    assert len(out['result']['service_candidates'])==len(catalog)
    assert {x['service_id'] for x in out['result']['service_candidates']}=={x['service_id'] for x in catalog}
    assert all(x['service_level']==0 for x in out['result']['service_candidates'])
    assert len(fake.calls)==1+((len(catalog)+4)//5)


def test_qualification_evidence_is_editable_and_removable(tmp_path):
    e=eng(tmp_path)
    p=create_professional_candidate(e,'Preuve Test',actor='admin')
    s=list_services(e,active_only=True)[0]
    eid=add_qualification_evidence(e,p,s['id'],'admin','AUTRE','preuve initiale')
    update_qualification_evidence(e,eid,'admin','AUTRE','preuve corrigée')
    d=get_person_service_qualification(e,p,s['id'])
    assert d['evidence'][0]['evidence_text']=='preuve corrigée'
    delete_qualification_evidence(e,eid,'admin')
    d=get_person_service_qualification(e,p,s['id'])
    assert d['evidence']==[]
    assert any(h['event_type']=='EVIDENCE_REMOVED' for h in d['history'])


def test_rc21_ui_exposes_ai_benefit_and_management_actions():
    import branding
    assert branding.APP_VERSION=='3.0.0-P5-RECETTE-RC1'
    src=open('app.py',encoding='utf-8').read()
    assert 'Résultat IA sur l’ensemble des prestations' in src
    assert 'Aucun élément repéré' in src
    assert 'Éléments repérés — niveau global bloqué' in src
    assert 'Préremplir l’évaluation à partir de l’analyse IA' in src
    assert 'Retirer / supprimer cette preuve' in src
    assert 'La dernière tentative d\'analyse a échoué' in src
