import ast
import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'app.py'


def fake_streamlit_module():
    st=types.ModuleType('streamlit')
    class SS(dict):
        __getattr__=dict.get
        def __setattr__(self,k,v): self[k]=v
    st.session_state=SS()
    st.secrets={}
    def cache_data(*args,**kwargs):
        def deco(fn): return fn
        return deco
    st.cache_data=cache_data
    def noop(*args,**kwargs): return None
    for name in ['info','warning','error','success','markdown','write','caption','metric','subheader','title','divider','rerun','set_page_config']:
        setattr(st,name,noop)
    sys.modules['streamlit']=st
    comp=types.ModuleType('streamlit.components')
    compv1=types.ModuleType('streamlit.components.v1'); compv1.html=noop
    sys.modules['streamlit.components']=comp; sys.modules['streamlit.components.v1']=compv1
    return st


def load_app():
    st=fake_streamlit_module()
    spec=importlib.util.spec_from_file_location('rv_app',APP)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod,st


def seed_state(mod,st):
    for k,v in mod.default_business_state().items(): st.session_state[k]=v
    st.session_state.update({
        'beneficiaire':{'prenom':'Dominique','nom':'Test','email':'d@example.com','consultant':'Coach'},
        'passation_id':'CL360-TEST-001','started_at':'2026-07-28T10:00:00','access_authorized':True,
        'existing_values':['Liberté'],'validated_app_values':['Respect'],
        'validation':{'Liberté':{'fondamentale':True},'Respect':{'fondamentale':True}},
        'personal_defs':{'Liberté':'Pouvoir choisir.','Respect':'Considérer les personnes.'},
        'value_records':{
            'Liberté':{'source':'accompagnateur','statut':'validee','situations_associees':['Choix professionnel'],'date_decouverte':'2026-07-01'},
            'Respect':{'source':'exploration_application','statut':'validee','situations_associees':['Échange difficile'],'date_decouverte':'2026-07-28'},
        },
        'beneficiary_profile':{'situation_actuelle':'En réflexion','objectif_demarche':'Clarifier mes valeurs'},
        'domains_explored':{'travail':2,'relations':1},
        'completion_check':{'representation':'Oui','angles_a_reprendre':'Priorités professionnelles'},
        'final_transmission_status':{},
    })


def test_python_ast_and_required_functions():
    tree=ast.parse(APP.read_text(encoding='utf-8'))
    names={n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    required={'open_response_widget','synchronize_value_state','final_pdf_from_payload','build_final_payload','render_resume_welcome'}
    assert required <= names


def test_final_payload_is_epure_and_regenerable():
    mod,st=load_app(); seed_state(mod,st)
    payload=mod.build_final_payload()
    assert payload['statut']=='parcours_cloture'
    assert payload['acces_autorise'] is True
    assert len(payload['valeurs_fondamentales'])==2
    forbidden={'conversation','questionnaires','transcriptions','pending_submission','code_secret','access_code'}
    assert not (forbidden & set(payload))
    raw=json.dumps(payload,ensure_ascii=False)
    assert 'Pouvoir choisir' in raw and 'Considérer les personnes' in raw
    pdf=mod.final_pdf_from_payload(payload)
    assert pdf[:4]==b'%PDF' and len(pdf)>2000


def test_work_payload_contains_access_flag_and_structured_answers():
    mod,st=load_app(); seed_state(mod,st)
    st.session_state.answer_metadata={'profile_x':{'version_officielle':'Texte validé','mode_saisie':'voix'}}
    payload=mod.build_payload(False)
    assert payload['acces_autorise'] is True
    assert payload['metier']['reponses_structurees']['profile_x']['mode_saisie']=='voix'


def test_sync_removes_false_validation():
    mod,st=load_app(); seed_state(mod,st)
    st.session_state.validation['Respect']['fondamentale']=False
    mod.synchronize_value_state()
    assert 'Respect' not in st.session_state.validated_app_values
    assert mod.validated_names()==['Liberté']


def test_interface_titles_have_no_visible_numbering():
    text=APP.read_text(encoding='utf-8')
    import re
    titles=re.findall(r'st\.title\("([^"]+)"\)',text)
    assert titles
    assert all(not re.match(r'^\d+[.)]?\s',t) for t in titles)
    assert 'Étape 10' not in text and 'Étape 11' not in text


def test_single_open_response_architecture_and_voice_cleanup():
    tree=ast.parse(APP.read_text(encoding='utf-8'))
    names={n.name for n in tree.body if isinstance(n,ast.FunctionDef)}
    assert {'clean_spoken_text','_local_spoken_cleanup','revise_exploration_turn','invalidate_dependencies','closure_consistency_audit'} <= names
    text=APP.read_text(encoding='utf-8')
    assert text.count('st.audio_input("Enregistrer ma réponse"')==1
    assert '_audio_fingerprint(audio)' in text
    assert 'already_done=' in text
    assert 'Transcription en cours…' in text
    assert 'Transcription initiale' in text
    assert 'Proposition corrigée Clarté360' in text
    assert 'Valider cette réponse orale' in text
    assert 'Valider ma réponse écrite' in text


def test_local_voice_cleanup_removes_fillers_and_immediate_repetition():
    mod,st=load_app(); seed_state(mod,st)
    cleaned=mod._local_spoken_cleanup("euh je je souhaite, euh, davantage de liberté liberté.")
    assert 'euh' not in cleaned.lower()
    assert 'je je' not in cleaned.lower()
    assert 'liberté liberté' not in cleaned.lower()
    assert 'liberté' in cleaned.lower()


def test_profile_change_invalidates_only_generated_exploration():
    mod,st=load_app(); seed_state(mod,st)
    st.session_state.value_records['Respect']['source']='exploration_application'
    st.session_state.conversation=[{'question':'Q','answer':'A'}]
    st.session_state.completion_check={'representation':'Oui'}
    mod.invalidate_dependencies('profile',reason='test')
    assert 'Liberté' in st.session_state.existing_values
    assert 'Respect' not in st.session_state.validation
    assert st.session_state.conversation==[]
    assert st.session_state.completion_check=={}
    assert 'controle_completude' in st.session_state.stale_sections


def test_value_definition_change_invalidates_that_validation_only():
    mod,st=load_app(); seed_state(mod,st)
    mod.invalidate_dependencies('value_definition',value_name='Respect',reason='test')
    assert 'Liberté' in st.session_state.validation
    assert 'Respect' not in st.session_state.validation
    assert 'Respect' not in st.session_state.validated_app_values
    assert st.session_state.hypothesis_status['Respect']=='en_cours_analyse'


def test_closure_audit_blocks_stale_or_missing_completion():
    mod,st=load_app(); seed_state(mod,st)
    st.session_state.stale_sections=['controle_completude']
    st.session_state.completion_check={}
    ok,issues=mod.closure_consistency_audit()
    assert ok is False
    assert len(issues)>=2


def test_work_json_contains_exact_resume_state_and_navigation():
    mod,st=load_app(); seed_state(mod,st)
    st.session_state.page='Validation'
    st.session_state.navigation_history=['Prerequis','Presentation beneficiaire','Validation']
    st.session_state.validation_stage={'Respect':2}
    st.session_state.hypothesis_queue=['Respect']
    payload=mod.build_payload(False)
    resume=payload['metier']['etat_reprise']
    assert resume['page']=='Validation'
    assert resume['navigation_history'][-1]=='Validation'
    assert resume['validation_stage']['Respect']==2
    assert resume['hypothesis_queue']==['Respect']
    raw=json.dumps(payload,ensure_ascii=False)
    assert 'access_code' not in raw and 'unlock_code' not in raw


def test_ai_calls_are_idempotent_and_retries_are_bounded():
    text=APP.read_text(encoding='utf-8')
    assert 'max_retries=0' in text
    assert 'for attempt in range(3)' not in text
    assert 'ai_request_log' in text
    assert 'ai_result_cache' in text
    assert 'audio_transcript_cache' in text

def test_rgpd_and_profile_question_are_updated():
    text=APP.read_text(encoding='utf-8')
    assert 'RGPD-Clarte360-RVC360-v2.1.2-2026-07' in text
    assert 'API OpenAI et non le service grand public ChatGPT' in text
    assert 'ne sont pas utilisées pour entraîner les modèles' in text
    assert 'votre âge, votre situation familiale, votre métier et vos principales activités' in text
