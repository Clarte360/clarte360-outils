"""P3: automated coverage for the context-first, vertical portal navigation.

Static interface contracts are deliberate: this isolated environment does not
install Streamlit or authenticate into the external Microsoft 365 tenant.
"""
from pathlib import Path
import ast
import re
import pytest

from navigation_p3 import (
    ADMIN_ACTION_SCREENS, ADMIN_PAGES, BENEFICIARY_SCREENS,
    TRAINER_SCREENS, action_rows, authorized_action_choice,
    preferred_screen, screens_for_role,
)

APP=Path('app.py').read_text(encoding='utf-8')
TREE=ast.parse(APP)


def _fn(name):
    return next(n for n in TREE.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)


def _direct_section_keys(name):
    out=[]
    for n in _fn(name).body:
        if not isinstance(n,ast.If):
            continue
        x=n.test
        if not (isinstance(x,ast.Compare) and isinstance(x.left,ast.Name)
                and x.left.id=='selected_section' and len(x.ops)==1
                and isinstance(x.ops[0],ast.Eq) and len(x.comparators)==1):
            continue
        if isinstance(x.comparators[0],ast.Constant):
            out.append(x.comparators[0].value)
    return out


@pytest.mark.parametrize('role,expected',[
    ('BENEFICIARY',12),('TRAINER',9),('ADMIN_ACTION',12)
])
def test_p3_all_portal_screens_registered(role,expected):
    sections=screens_for_role(role)
    assert len(sections)==expected
    assert len({s.key for s in sections})==expected
    assert all(s.label and s.title for s in sections)


def test_beneficiary_needs_an_action_for_private_sections():
    assert [s.key for s in screens_for_role('BENEFICIARY',action_selected=False)]==['home','profile']
    assert {s.key for s in screens_for_role('BENEFICIARY',action_selected=True)} >= {'teams','tools','documents','courses','signatures','archives'}


@pytest.mark.parametrize('role', ['BENEFICIARY','TRAINER','ADMIN_ACTION'])
def test_default_and_invalid_navigation_does_not_select_hidden_screen(role):
    sections=screens_for_role(role)
    assert preferred_screen(sections,None)==sections[0].key
    assert preferred_screen(sections,'wrong')==sections[0].key
    assert preferred_screen(sections,sections[-1].key)==sections[-1].key


@pytest.mark.parametrize('role', ['VISITOR','ROOT',''])
def test_p3_does_not_open_client_or_unknown_area(role):
    with pytest.raises(ValueError):screens_for_role(role)


@pytest.mark.parametrize('candidate,expected',[
    (3,3),('4',4),('099',None),(-1,None),(None,None),('joe',None),('',None)
])
def test_revoked_or_unknown_actions_are_not_reselected(candidate,expected):
    assert authorized_action_choice([3,4],candidate)==expected


def test_action_scope_filters_approved_rows_without_widening_access():
    rows=[{'action_id':3,'n':'A'},{'action_id':4,'n':'B'},{'action_id':3,'n':'C'},{'action_id':None,'n':'GLOBAL'}]
    assert [r['n'] for r in action_rows(rows,3)]==['A','C']
    assert [r['n'] for r in action_rows(rows,4)]==['B']
    assert action_rows(rows,8)==[]
    assert len(action_rows(rows,None))==4


@pytest.mark.parametrize('section',BENEFICIARY_SCREENS)
def test_each_beneficiary_screen_is_actually_rendered(section):
    assert section.key in _direct_section_keys('beneficiary_portal_page')


@pytest.mark.parametrize('section',TRAINER_SCREENS)
def test_each_trainer_screen_is_actually_rendered(section):
    assert section.key in _direct_section_keys('render_trainer_action')


def test_admin_action_sections_preserve_exact_original_business_handlers():
    node=_fn('action_detail')
    assigns=[n for n in node.body if isinstance(n,ast.Assign)
             and any(isinstance(t,ast.Name) and t.id=='tab_specs' for t in n.targets)]
    assert len(assigns)==1
    value=assigns[0].value
    assert isinstance(value,ast.List)
    real=[(el.elts[0].value,el.elts[1].id) for el in value.elts]
    assert [k for k,fn in real]==[s.key for s in ADMIN_ACTION_SCREENS]
    for _,fn in real:
        assert fn in {node.name for node in TREE.body if isinstance(node,ast.FunctionDef)}


def test_admin_global_pages_keep_all_historic_routes():
    assert set(ADMIN_PAGES) >= {'Tableau de bord','Nouvelle action','Importer une action','Actions','Relances','Qualité','Études PIP/O*NET','Contacts / Prospects','Intervenants / Partenaires','Paramètres'}
    assert 'Espace Client / DRH' in ADMIN_PAGES
    for page in ADMIN_PAGES:
        assert ("page=='"+page+"'") in APP


def test_three_primary_portals_do_not_instantiate_all_tabs():
    for name in ('render_trainer_action','beneficiary_portal_page','action_detail'):
        block=ast.get_source_segment(APP,_fn(name))
        assert 'st.tabs(' not in block
        assert '_p3_sidebar_section(' in block


def test_teams_and_pip_still_have_explicit_portal_views():
    trainer=ast.get_source_segment(APP,_fn('render_trainer_action'))
    beneficiary=ast.get_source_segment(APP,_fn('beneficiary_portal_page'))
    admin=ast.get_source_segment(APP,_fn('action_detail'))
    assert "if selected_section=='teams':" in trainer
    assert "if selected_section=='teams':" in beneficiary
    assert 'action_teams' in admin
    assert 'teams_participant_evidence' in beneficiary
    assert 'build_pip_prescription_launch' in beneficiary
    assert 'build_ipip_prescription_launch' in beneficiary
    assert 'trainer_countersign_tasks' in APP
    assert 'teams_attendance_reconciliation' in APP


def test_action_is_chosen_before_showing_private_sections():
    body=ast.get_source_segment(APP,_fn('beneficiary_portal_page'))
    assert body.index("selected_action_id=st.sidebar.selectbox") < body.index("selected_section=_p3_sidebar_section('BENEFICIARY'")
    assert body.index("selected_section=_p3_sidebar_section('BENEFICIARY'") < body.index("if selected_section=='home':")
    assert "st.session_state['_p3_next_beneficiary_action']" in body
    assert 'action_rows(docs,selected_action_id)' in body
    assert 'action_rows(prescriptions,selected_action_id)' in body
    assert 'action_rows(doc_notifications,selected_action_id)' in body


def test_trainer_and_admin_select_action_in_sidebar():
    assert "st.sidebar.selectbox('Action \u00e0 ouvrir'" in APP
    assert "st.sidebar.selectbox('Choisir une action'" in APP
    assert "st.sidebar.radio('Navigation du dossier'" in APP
    assert "st.session_state['p3_admin_action_id']" in APP


def test_client_scope_is_opened_only_by_explicit_p4():
    nav=Path('navigation_p3.py').read_text(encoding='utf-8')
    assert 'CLIENT' not in [s.key for s in BENEFICIARY_SCREENS]
    assert 'CLIENT' not in [s.key for s in ADMIN_ACTION_SCREENS]
    assert "role == 'ADMIN_ACTION'" in nav
    assert "role == 'CLIENT'" in nav
    assert 'CLIENT_SCREENS' in nav


def test_unchanged_security_services_preserved_in_zip():
    assert Path('services.py').exists()
    assert Path('db.py').exists()
    assert Path('worker.py').exists()
    assert Path('graph_client.py').exists()
    assert Path('persistent_session.py').exists()
    assert 'read_document_for_actor' in APP
    assert 'store_document_for_actor' in APP
    assert 'export_action_documents_zip' in APP


def test_irreversible_action_deletion_is_only_on_settings_page():
    source=ast.get_source_segment(APP,_fn('actions_list'))
    assert "if st.session_state.get(f'p3_screen_admin_action_{aid}')=='action_parametres':" in source
    assert 'purge_action(ENGINE,aid' in source


def test_newly_created_action_is_selected_in_context():
    source=ast.get_source_segment(APP,_fn('create_action_screen'))
    assert "st.session_state['p3_admin_action_id']=aid" in source
    assert "st.session_state.selected_action=aid" in source
