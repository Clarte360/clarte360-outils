"""J5: two real admin spaces, contextual action navigation and large lists."""
from pathlib import Path
import ast
import pytest
from admin_navigation import (
    WORKSPACE_ACTIONS, WORKSPACE_GENERAL, WORKSPACE_HOME,
    GENERAL_PAGES, ACTION_PAGES, PAGE_SIZE, workspace_for_route,
    pages_for_workspace, valid_route, filter_sort_actions, page_slice,
    action_label, action_list_rows,
)

APP=Path('app.py').read_text(encoding='utf-8')
TREE=ast.parse(APP)

def function_body(name):
    fn=next(node for node in TREE.body if isinstance(node,ast.FunctionDef) and node.name==name)
    return ast.get_source_segment(APP,fn)

@pytest.mark.parametrize('page', ['Actions','Nouvelle action','Importer une action'])
def test_actions_routes_go_to_actions_workspace(page):
    assert workspace_for_route(page)==WORKSPACE_ACTIONS

@pytest.mark.parametrize('page', ['Relances','Qualité','Intervenants / Partenaires',
                                  'Paramètres','Espace Client / DRH','Contacts / Prospects'])
def test_general_routes_go_to_general_workspace(page):
    assert workspace_for_route(page)==WORKSPACE_GENERAL

def test_two_disjoint_workspaces_and_distinct_dashboards():
    assert pages_for_workspace(WORKSPACE_HOME)==()
    assert set(GENERAL_PAGES)&set(ACTION_PAGES)=={'Tableau de bord'}
    assert 'Actions' not in GENERAL_PAGES
    assert {'Nouvelle action','Importer une action','Actions'} <= set(ACTION_PAGES)
    assert 'Qualité' not in ACTION_PAGES
    assert valid_route(WORKSPACE_ACTIONS,'Qualité')=='Tableau de bord'
    assert valid_route(WORKSPACE_GENERAL,'Actions')=='Tableau de bord'

def test_valid_internal_switch_does_not_expand_privileges():
    assert 'ADMIN_ACTION_SCREENS' in Path('navigation_p3.py').read_text(encoding='utf-8')
    assert "_p3_sidebar_section('ADMIN_ACTION',action_id=aid" in APP
    assert 'st.session_state[\'admin_workspace\']' in APP
    assert "_request_admin_workspace(WORKSPACE_HOME)" in APP
    assert 'Confirmer le changement' in APP

def test_all_j4_notifications_still_have_destination():
    body=function_body('_j4_notification_destination')
    assert "st.session_state['admin_workspace']=WORKSPACE_GENERAL" in body
    assert "st.session_state['admin_workspace']=WORKSPACE_ACTIONS" in body
    assert "st.session_state['admin_actions_view']='detail'" in body
    assert "st.session_state['p3_admin_action_id']=int(aid)" in body

def test_no_duplicate_action_settings_title_from_context_sidebar():
    assert 'show_title=False' in function_body('action_detail')
    assert "st.subheader('Paramètres de l’action')" in function_body('action_settings_tab')

def test_selected_action_retains_all_twelve_business_handlers_and_purge_guard():
    b=function_body('action_detail')
    assert b.count("('action_")>=12
    assert "if st.session_state.get(f'p3_screen_admin_action_{aid}')=='action_parametres':" in function_body('actions_list')
    assert 'purge_action(ENGINE,aid' in function_body('actions_list')
    assert "st.sidebar.selectbox('Choisir une action'" in APP

def test_active_priority_archives_hidden_and_year_type_filter():
    rows=[{'id':1,'status':'ARCHIVEE','start_date':'2026-12-01','prestation_type':'COACHING'},
          {'id':2,'status':'BROUILLON','start_date':'2026-02-01','prestation_type':'FORMATION'},
          {'id':3,'status':'ACTIVE','start_date':'2026-01-01','prestation_type':'FORMATION'},
          {'id':4,'status':'ACTIVE','start_date':'2026-05-01','prestation_type':'FORMATION'},
          {'id':5,'status':'CLOTUREE','start_date':'2025-05-01','prestation_type':'COACHING'}]
    assert [r['id'] for r in filter_sort_actions(rows)] == [4,3,2,5]
    assert [r['id'] for r in filter_sort_actions(rows,include_archived=True)] == [4,3,2,5,1]
    assert [r['id'] for r in filter_sort_actions(rows,year='2026',prestation='FORMATION')] == [4,3,2]
    assert [r['id'] for r in filter_sort_actions(rows,status='ACTIVE')] == [4,3]

def test_first_participant_and_client_context_search():
    acts=[dict(id=3,action_no='CLA0003',title='Bilan de compétences',client_name='Entreprise Bleu',status='ACTIVE')]
    summ={3:{'participant_count':12,'first_participant':'Marine Petit'}}
    rows=action_list_rows(acts,summ)
    assert rows[0]['participant_count']==12
    assert 'Entreprise Bleu' in action_label(rows[0])
    assert '12 stagiaires' in action_label(rows[0])
    assert 'Marine Petit' in action_label(rows[0])
    assert filter_sort_actions(rows,term='petit') == rows
    assert filter_sort_actions(rows,term='bleu') == rows

def test_real_first_stagiaire_query_is_single_sql_and_ordered():
    b=function_body('_j5_action_participants_summary')
    assert 'SELECT a.id action_id' in b
    assert 'ORDER BY p.id LIMIT 1' in b
    assert 'COUNT(*)' in b
    assert 'FROM actions a' in b

def test_200_actions_have_eight_pages_and_clamped_page():
    rows=[{'id':i} for i in range(200)]
    first,page,total=page_slice(rows,page=1,size=PAGE_SIZE)
    assert (len(first),page,total)==(25,1,8)
    last,page,total=page_slice(rows,page=100,size=PAGE_SIZE)
    assert (len(last),page,total)==(25,8,8)
    assert page_slice(rows,page=3,size=50)[2]==4
    with pytest.raises(ValueError):page_slice(rows,size=500)

def test_no_duplicate_table_when_detail_opened():
    b=function_body('actions_list')
    assert "if st.session_state.get('admin_actions_view')!='detail':" in b
    assert 'action_detail(aid)' in b
    assert 'j5_return_list' in b
    assert 'j5_page_index' in b
    assert 'search_actions(ENGINE,term,include_archived=True)' in b

def test_dashboard_has_only_five_recent_actions_and_switch_links():
    b=function_body('dashboard')
    assert 'actions[:5]' in b
    assert "_next_nav']='Actions'" in b
    assert "_next_nav']='Nouvelle action'" in b
    assert "_next_nav']='Importer une action'" in b

def test_route_into_general_client_and_back_preserves_client_portal():
    assert 'Espace Client / DRH' in GENERAL_PAGES
    assert 'admin_client_portal_screen' in APP
    assert 'grant_client_action' in APP
    assert 'client_portal_identity' in APP
