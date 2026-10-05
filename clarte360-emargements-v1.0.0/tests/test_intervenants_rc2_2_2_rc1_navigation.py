from db import make_engine, init_db, execute, utcnow_iso
from services import (
    create_professional_intervenant, list_services, set_action_service_requirement,
    set_human_service_qualification, action_professional_eligibility,
)
from workflow_navigation import (
    prepare_action_qualification_navigation,
    mark_qualification_saved_for_action,
    prepare_return_to_action,
)


def _business_context(tmp_path):
    e = make_engine('sqlite:///' + str(tmp_path / 'rc1_nav.db'))
    init_db(e)
    svc = list_services(e, True)[0]
    ppid = create_professional_intervenant(
        e, 'Test C5 UI', email='c5-ui@example.test',
        collaboration_type='A_DEFINIR', actor='admin@test'
    )
    n = utcnow_iso()
    aid = execute(
        e,
        "INSERT INTO actions(action_no,title,nature,mode,status,created_at,updated_at) "
        "VALUES('RC-C5','Action C5 UI','FORMATION','PRESENTIEL','BROUILLON',:n,:n)",
        {'n': n},
    )
    set_action_service_requirement(e, aid, svc['id'], 'admin@test', 3, False)
    return e, aid, ppid, svc


def test_c5_navigation_state_action_to_exact_qualification_and_back(tmp_path):
    e, aid, ppid, svc = _business_context(tmp_path)
    state = {}

    before = action_professional_eligibility(e, aid, ppid)
    assert before['status'] == 'NON_QUALIFIE' and not before['eligible']

    prepare_action_qualification_navigation(state, aid, ppid, svc['id'])
    assert state['_next_nav'] == 'Intervenants / Partenaires'
    assert state['_j2_open_ppid'] == ppid
    assert state['_j17_focus_service_id'] == svc['id']
    assert state['_rc222_return_action_id'] == aid
    assert state['_rc222_return_action_ppid'] == ppid
    assert state['_rc222_return_action_service_id'] == svc['id']

    set_human_service_qualification(e, ppid, svc['id'], 3, 'admin@test', 'Validation C5 RC1', True)
    assert mark_qualification_saved_for_action(state, ppid)
    after = action_professional_eligibility(e, aid, ppid)
    assert after['status'] == 'QUALIFIE' and after['eligible']

    prepare_return_to_action(state, aid, after['eligible'], after['reason'], after['status'])
    assert state['selected_action'] == aid
    assert state['_rc222_action_focus_tab'] == 'Intervenants'
    assert state['_next_nav'] == 'Actions'
    assert state['_action_flash'][1] == 'success'
    assert 'Éligibilité recalculée' in state['_action_flash'][2]
    assert '_rc222_return_action_id' not in state
    assert '_rc222_return_action_ppid' not in state
    assert '_rc222_return_action_service_id' not in state


def test_c5_return_keeps_warning_when_requirements_remain_unsatisfied(tmp_path):
    e, aid, ppid, svc = _business_context(tmp_path)
    state = {}
    prepare_action_qualification_navigation(state, aid, ppid, svc['id'])
    set_human_service_qualification(e, ppid, svc['id'], 2, 'admin@test', 'Niveau insuffisant', True)
    after = action_professional_eligibility(e, aid, ppid)
    assert after['status'] == 'NIVEAU_INSUFFISANT' and not after['eligible']
    prepare_return_to_action(state, aid, after['eligible'], after['reason'], after['status'])
    assert state['_action_flash'][1] == 'warning'
    assert state['_next_nav'] == 'Actions'
