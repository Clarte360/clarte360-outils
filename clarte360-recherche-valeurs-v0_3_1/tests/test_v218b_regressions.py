import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT=Path(__file__).resolve().parents[1]

class Session(dict):
    __getattr__=dict.get
    def __setattr__(self,k,v): self[k]=v

class DummyStreamlit(ModuleType):
    def __init__(self):
        super().__init__('streamlit'); self.session_state=Session(); self.secrets={}
    def cache_data(self,*a,**k):
        def deco(fn): return fn
        return deco
    def __getattr__(self,name):
        if name=='sidebar': return self
        return lambda *a,**k: False


def load_app():
    st=DummyStreamlit(); sys.modules['streamlit']=st
    comp=ModuleType('streamlit.components.v1'); comp.html=lambda *a,**k: None
    comps=ModuleType('streamlit.components'); comps.v1=comp
    st.components=comps
    sys.modules['streamlit.components']=comps
    sys.modules['streamlit.components.v1']=comp
    spec=importlib.util.spec_from_file_location('app_v218b',ROOT/'app.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod,st


def seed(mod,st):
    for k,v in mod.default_business_state().items(): st.session_state[k]=v
    st.session_state.beneficiaire={'prenom':'SOLANGE','nom':'PAQUETTE'}
    st.session_state.validation={
        'Clarté':{'fondamentale':True},
        'Liberté':{'fondamentale':True},
    }
    st.session_state.existing_values=['Clarté']
    st.session_state.validated_app_values=['Liberté']
    st.session_state.personal_defs={'Clarté':'définition','Liberté':'définition'}


def test_review_item_is_idempotent():
    mod,st=load_app(); seed(mod,st)
    work={'nom_final':'Clarté','definition_personnelle':'définition','source':'accompagnateur'}
    assert mod._add_review_item(work,'demande') is True
    assert mod._add_review_item(work,'demande') is False
    assert len(st.session_state.session_review_items)==1


def test_old_in_progress_value_becomes_value_to_examine():
    mod,st=load_app(); seed(mod,st)
    st.session_state.prerequisite_confirmed=True
    st.session_state.value_records={
        'La securité financier':{
            'nom_propose':'La securité financier',
            'statut':'en_cours_analyse',
            'definition_personnelle':"Peur d'être en manque financière",
            'situations_associees':['situation'],
        }
    }
    st.session_state.discarded=['La securité financier']
    mod._ensure_migrated_state()
    assert len(st.session_state.values_to_examine)==1
    assert 'securite' in mod.normalize(st.session_state.values_to_examine[0]['nom_initial'])
    mod._ensure_migrated_state()
    assert len(st.session_state.values_to_examine)==1


def test_completed_prerequisite_is_never_reopened_by_migration():
    mod,st=load_app(); seed(mod,st)
    st.session_state.prerequisite_confirmed=True
    mod._ensure_migrated_state()
    assert st.session_state.module_states['module_1']['status']=='termine'


def test_default_lands_on_modules_home():
    mod,st=load_app()
    assert mod.default_business_state()['active_module']=='accueil_modules'
