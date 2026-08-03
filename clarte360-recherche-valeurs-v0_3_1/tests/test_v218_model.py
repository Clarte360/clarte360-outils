import importlib.util
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
    st.session_state=SS(); st.secrets={}
    def cache_data(*args,**kwargs):
        def deco(fn): return fn
        return deco
    st.cache_data=cache_data
    def noop(*args,**kwargs): return None
    for name in ['info','warning','error','success','markdown','write','caption','metric','subheader','title','divider','rerun','set_page_config']:
        setattr(st,name,noop)
    sys.modules['streamlit']=st
    comp=types.ModuleType('streamlit.components'); compv1=types.ModuleType('streamlit.components.v1'); compv1.html=noop
    sys.modules['streamlit.components']=comp; sys.modules['streamlit.components.v1']=compv1
    return st


def load_app():
    st=fake_streamlit_module()
    spec=importlib.util.spec_from_file_location('rv_app_v218',APP)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod,st


def seed(mod,st):
    for k,v in mod.default_business_state().items(): st.session_state[k]=v
    st.session_state.update({'beneficiaire':{'prenom':'Test','nom':'Clarté','email':'x@y.fr'},'access_authorized':True,'passation_id':'TEST','session_history':[]})


def test_version_and_dynamic_referential():
    mod,st=load_app()
    assert mod.APP_VERSION=='2.1.3.9F3-preproduction'
    assert len(mod.CATALOGUE)==204
    assert mod.value_info('Clarté')['code']=='RVC360-241'


def test_new_schema_defaults_present():
    mod,st=load_app(); d=mod.default_business_state()
    assert d['json_schema_version']=='2.1.3.9D'
    assert set(d['module_states'])=={'module_1','module_2','module_3','module_4','module_5'}
    assert d['central_validated_values']==[] and d['values_to_examine']==[] and d['session_review_items']==[]


def test_central_value_is_single_report_source():
    mod,st=load_app(); seed(mod,st)
    mod._upsert_central_value('Clarté','Pouvoir ordonner mes idées.','accompagnateur',definition_clarte360=mod.value_info('Clarté')['definition'],protected=True)
    assert mod.validated_names()==['Clarté']
    assert st.session_state.central_validated_values[0]['protected'] is True
    assert st.session_state.module_states['module_5']['status']=='disponible'


def test_old_state_migrates_without_loss():
    mod,st=load_app(); seed(mod,st)
    st.session_state.existing_values=['Liberté']; st.session_state.validation={'Liberté':{'fondamentale':True}}; st.session_state.personal_defs={'Liberté':'Pouvoir choisir.'}; st.session_state.prerequisite_confirmed=True
    mod._ensure_migrated_state()
    assert mod.validated_names()==['Liberté']
    assert st.session_state.central_validated_values[0]['source']=='accompagnateur'
    assert st.session_state.module_states['module_1']['status']=='termine'


def test_work_json_contains_new_transversal_lists():
    mod,st=load_app(); seed(mod,st)
    mod._upsert_central_value('Clarté','Pouvoir ordonner mes idées.','manuel',definition_clarte360=mod.value_info('Clarté')['definition'])
    st.session_state.values_to_examine=[{'nom_final':'Respect','statut':'a_examiner'}]
    st.session_state.session_review_items=[{'terme':'Contrôle','statut':'a_revoir_en_seance'}]
    payload=mod.build_payload(False); m=payload['metier']
    assert m['schema_metier']=='2.1.3.8E'
    assert m['valeurs_validees_centrales'][0]['nom_final']=='Clarté'
    assert m['valeurs_a_examiner'][0]['nom_final']=='Respect'
    assert m['a_revoir_en_seance'][0]['terme']=='Contrôle'


def test_no_real_secrets_in_project():
    forbidden=('sk'+'-proj-','Contact'+'Clarte360'+'2026#1977')
    for path in ROOT.rglob('*'):
        if path.is_file() and path.suffix.lower() in {'.py','.toml','.md','.txt','.json'}:
            text=path.read_text(encoding='utf-8',errors='ignore')
            assert not any(token in text for token in forbidden), path
