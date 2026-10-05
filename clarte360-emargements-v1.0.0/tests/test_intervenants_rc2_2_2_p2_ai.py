import json
import sys
from types import SimpleNamespace

from db import make_engine, init_db
from qualification_ai import GlobalDossierAIGateway, inspect_pdf_for_ai
from services import (
    create_professional_intervenant, list_services, list_service_criteria,
    save_global_professional_ai_analysis, latest_global_professional_ai_run,
    list_qualification_review_points,
)


def eng():
    e=make_engine('sqlite:///:memory:')
    init_db(e)
    return e


def facts_payload():
    return {
        'profile': {'title': None, 'summary': None, 'specialties': []},
        'experiences': [], 'education': [], 'certifications': [], 'languages': [],
        'identity_alerts': [], 'missing_points': [],
    }


class Response:
    def __init__(self, payload, in_tokens=10, out_tokens=5):
        self.status='completed'
        self.output_text=json.dumps(payload)
        self.usage=SimpleNamespace(input_tokens=in_tokens, output_tokens=out_tokens)


def test_p2_false_zero_is_lifted_when_positive_criterion_exists_and_mandatory_gap_is_separate():
    service={'service_id': 7, 'name':'Bilan test', 'criteria':[
        {'criterion_id': 70, 'label':'Pratique', 'required':True, 'minimum_level':3},
        {'criterion_id': 71, 'label':'Confidentialité', 'required':True, 'minimum_level':2},
    ]}
    class Responses:
        def create(self, **kwargs):
            name=kwargs['text']['format']['name']
            if name=='dossier_professionnel_faits':
                return Response(facts_payload())
            return Response({'service_candidates':[{
                'service_id':7, 'service_level':0, 'confidence':.8,
                'rationale':'Un obligatoire manque', 'source_document_ids':[1],
                'missing_points':['Confirmer la confidentialité'],
                'evidence':[{'source':'CV','fact':'Pratique démontrée','supports_level':3,'document_id':1,'criterion_ids':[70],'identity_status':'COHERENT'}],
                'criteria':[
                    {'criterion_id':70,'proposed_level':3,'confidence':.8,'rationale':'Expérience','evidence_indexes':[0]},
                    {'criterion_id':71,'proposed_level':0,'confidence':.5,'rationale':'Non démontré','evidence_indexes':[]},
                ]
            }]})
    g=GlobalDossierAIGateway('', 'gpt-test', client=SimpleNamespace(responses=Responses()))
    out=g.analyze({'documents':[], 'service_catalog':[service]})
    c=out['result']['service_candidates'][0]
    assert c['service_level']==1
    assert c['service_level_adjusted'] is True
    assert c['required_criteria_total']==2
    assert c['required_criteria_positive']==1
    assert c['required_criteria_below_min'][0]['criterion_id']==71


def test_p2_zero_remains_zero_when_no_positive_fact_exists():
    service={'service_id': 8, 'name':'Sans preuve', 'criteria':[{'criterion_id':80,'label':'Critère','required':True,'minimum_level':2}]}
    class Responses:
        def create(self, **kwargs):
            if kwargs['text']['format']['name']=='dossier_professionnel_faits':
                return Response(facts_payload())
            return Response({'service_candidates':[{
                'service_id':8,'service_level':0,'confidence':.9,'rationale':'Aucun élément','source_document_ids':[],
                'missing_points':['Document manquant'],'evidence':[],
                'criteria':[{'criterion_id':80,'proposed_level':0,'confidence':.9,'rationale':'Aucun élément','evidence_indexes':[]}]
            }]})
    g=GlobalDossierAIGateway('', 'gpt-test', client=SimpleNamespace(responses=Responses()))
    c=g.analyze({'documents':[], 'service_catalog':[service]})['result']['service_candidates'][0]
    assert c['service_level']==0
    assert c['service_level_adjusted'] is False


def test_p2_global_gateway_counts_real_calls_retries_tokens_and_duration(monkeypatch):
    monkeypatch.setenv('CLARTE360_OPENAI_INPUT_USD_PER_MILLION','1.0')
    monkeypatch.setenv('CLARTE360_OPENAI_OUTPUT_USD_PER_MILLION','2.0')
    service={'service_id': 9, 'name':'Test', 'criteria':[]}
    class Responses:
        def __init__(self): self.n=0
        def create(self, **kwargs):
            self.n+=1
            if self.n==1:
                raise RuntimeError('transient')
            if kwargs['text']['format']['name']=='dossier_professionnel_faits':
                return Response(facts_payload(),100,20)
            return Response({'service_candidates':[{
                'service_id':9,'service_level':0,'confidence':.8,'rationale':'Aucun élément','source_document_ids':[],
                'missing_points':[],'evidence':[],'criteria':[]
            }]},50,10)
    responses=Responses()
    g=GlobalDossierAIGateway('', 'gpt-test', client=SimpleNamespace(responses=responses))
    out=g.analyze({'documents':[], 'service_catalog':[service]})
    m=out['run_metrics']
    assert m['api_call_count']==3
    assert m['retry_count']==1
    assert m['input_tokens']==150 and m['output_tokens']==30 and m['total_tokens']==180
    assert m['duration_seconds']>=0
    assert abs(m['estimated_cost'] - 0.00021) < 1e-9


def test_p2_pdf_page_inspection_detects_hybrid_without_ocr(tmp_path, monkeypatch):
    p=tmp_path/'hybrid.pdf'; p.write_bytes(b'%PDF fake')
    class Page:
        def __init__(self, text): self.text=text
        def extract_text(self): return self.text
    class Reader:
        def __init__(self, _): self.pages=[Page('Texte exploitable '*5), Page('')]
    monkeypatch.setitem(sys.modules,'pypdf',SimpleNamespace(PdfReader=Reader))
    info=inspect_pdf_for_ai(str(p), min_text_chars_per_page=30)
    assert info['text_pages']==1 and info['visual_pages']==1
    assert info['is_hybrid'] is True and info['needs_multimodal'] is True
    assert 'Texte exploitable' in info['text']


def test_p2_metrics_persist_and_new_missing_points_are_actionable():
    e=eng()
    p=create_professional_intervenant(e,'P2 Metrics',actor='admin')
    service=list_services(e,active_only=True)[0]
    criteria=list_service_criteria(e,service['id'],active_only=True)
    result={**facts_payload(), 'service_candidates':[{
        'service_id':service['id'],'service_level':1,'confidence':.5,'rationale':'Partiel','source_document_ids':[],
        'missing_points':['Vérifier expérience récente'],'evidence':[],
        'criteria':[{'criterion_id':c['id'],'proposed_level':0,'confidence':.4,'rationale':'A confirmer','evidence_indexes':[]} for c in criteria]
    }]}
    save_global_professional_ai_analysis(
        e,p,result,'admin','openai','gpt-test','p2','hash',SimpleNamespace(input_tokens=120,output_tokens=30),[],
        {'duration_seconds':12.5,'api_call_count':7,'retry_count':1,'total_tokens':150,'estimated_cost':0.01}
    )
    run=latest_global_professional_ai_run(e,p)
    assert run['duration_seconds']==12.5 and run['api_call_count']==7 and run['retry_count']==1
    assert run['total_tokens']==150 and abs(run['estimated_cost']-.01)<1e-9
    pts=list_qualification_review_points(e,p,service['id'],open_only=True)
    assert any(x['source']=='IA' and x['label']=='Vérifier expérience récente' for x in pts)


def test_p2_app_uses_hybrid_pdf_inspection_and_passes_run_metrics():
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
    assert 'inspect_pdf_for_ai' in src
    assert "pdf_info.get('is_hybrid')" in src
    assert "res.get('run_metrics')" in src
    assert 'Détails techniques IA' in src
