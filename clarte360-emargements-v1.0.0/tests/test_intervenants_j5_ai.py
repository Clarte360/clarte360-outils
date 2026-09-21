import json
from types import SimpleNamespace
from db import make_engine, init_db, one
from services import (
    create_professional_intervenant, list_services, set_human_service_qualification,
    save_ai_qualification_proposal, get_person_service_qualification,
    build_ai_qualification_payload, list_ai_analysis_runs
)
from qualification_ai import QualificationAIGateway, PROMPT_VERSION


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e


def fake_result(level=3, confidence=.82):
    return {
      'service_level':level,'confidence':confidence,'rationale':'Expériences cohérentes, à valider humainement.',
      'evidence':[{'source':'CV','fact':'Expérience déclarée et documentée','supports_level':level}],
      'missing_points':['Vérifier une référence récente'],'criteria':[]
    }


def test_gateway_uses_structured_response_without_secret_in_payload():
    payload={'person':{'title':'Consultant'},'service':{'name':'Conseil stratégique'},'criteria':[]}
    class Responses:
        def create(self, **kwargs):
            assert kwargs['store'] is False
            assert kwargs['text']['format']['type']=='json_schema'
            return SimpleNamespace(status='completed',output_text=json.dumps(fake_result()),usage=SimpleNamespace(input_tokens=100,output_tokens=50))
    client=SimpleNamespace(responses=Responses())
    g=QualificationAIGateway('', 'gpt-test', client=client)
    out=g.analyze(payload)
    assert out['result']['service_level']==3
    assert out['prompt_version']==PROMPT_VERSION and out['provider']=='openai'


def test_ai_proposal_never_overwrites_locked_human_validation():
    e=eng(); s=list_services(e,active_only=True)[0]; p=create_professional_intervenant(e,'IA Test',actor='admin@test')
    set_human_service_qualification(e,p,s['id'],4,'admin@test','Décision humaine',True)
    save_ai_qualification_proposal(e,p,s['id'],fake_result(2,.61),'admin@test','openai','gpt-test',PROMPT_VERSION,'abc')
    q=get_person_service_qualification(e,p,s['id'])['qualification']
    assert q['human_value']==4 and q['human_locked']==1
    assert q['ai_value']==2 and abs(q['ai_confidence']-.61)<.001


def test_reanalysis_changes_only_ai_side_and_keeps_history():
    e=eng(); s=list_services(e,active_only=True)[0]; p=create_professional_intervenant(e,'IA Reanalyse',actor='admin@test')
    set_human_service_qualification(e,p,s['id'],3,'admin@test','Autonome',True)
    save_ai_qualification_proposal(e,p,s['id'],fake_result(2,.55),'admin@test','openai','m1',PROMPT_VERSION,'h1')
    save_ai_qualification_proposal(e,p,s['id'],fake_result(4,.76),'admin@test','openai','m2',PROMPT_VERSION,'h2')
    q=get_person_service_qualification(e,p,s['id'])
    assert q['qualification']['human_value']==3
    assert q['qualification']['ai_value']==4
    assert len(list_ai_analysis_runs(e,p,s['id']))==2
    assert len([x for x in q['history'] if x['event_type']=='AI_PROPOSAL'])==2


def test_payload_is_minimized_and_does_not_include_contact_coordinates():
    e=eng(); s=list_services(e,active_only=True)[0]; p=create_professional_intervenant(e,'Minimisation IA','secret@example.test','0600000000',actor='admin@test')
    payload=build_ai_qualification_payload(e,p,s['id'],[])
    raw=json.dumps(payload)
    assert 'secret@example.test' not in raw
    assert '0600000000' not in raw
    assert payload['person']['professional_person_id']==p
