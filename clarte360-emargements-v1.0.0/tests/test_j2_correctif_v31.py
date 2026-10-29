from pathlib import Path
from db import make_engine, init_db, execute, utcnow_iso
from services import upsert_tool_catalog, list_tool_catalog, create_quality_event, add_quality_event_action, quality_general_action_plan

def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e

def test_tools_are_visible_for_every_action_type_despite_legacy_metadata():
    e=eng(); upsert_tool_catalog(e,{'tool_code':'ANY','name':'Any','base_url':'https://example.org','compatible_prestations':['COACHING']},'admin')
    for prestation in ['FORMATION','BILAN_COMPETENCES','VAE','COACHING','MENTORAT','AUTRE']:
        assert any(x['tool_code']=='ANY' for x in list_tool_catalog(e,prescription_only=True,prestation_type=prestation))

def test_general_action_plan_consolidates_capa():
    e=eng(); n=utcnow_iso(); oid=execute(e,"INSERT INTO organizations(name,legal_name,active,created_at,updated_at) VALUES('O','O',1,:n,:n)",{'n':n}); aid=execute(e,"INSERT INTO actions(action_no,title,nature,prestation_type,mode,status,planned_hours,expected_participants,organization_id,created_at,updated_at) VALUES('A-1','Titre','Formation','FORMATION','INDIVIDUEL','ACTIVE',1,1,:o,:n,:n)",{'o':oid,'n':n})
    ev=create_quality_event(e,'EXPRESSION','DIFFICULTE','Sujet','Description','admin',action_id=aid)
    add_quality_event_action(e,ev,'Corriger','admin',owner_name='Dominique')
    rows=quality_general_action_plan(e,aid)
    assert rows and rows[0]['action_no']=='A-1' and rows[0]['action_title_capa']=='Corriger'

def test_dashboard_no_longer_duplicates_quality_pilotage_and_countersign_private_helper_imported():
    src=Path('app.py').read_text(encoding='utf-8')
    dash=src[src.index('def dashboard():'):src.index('def actions_list():')]
    assert "st.subheader('Pilotage qualité')" not in dash
    assert 'from services import _duration_hms, _slot_participant_states' in src
    assert "Suivi du plan d'action général" in src
