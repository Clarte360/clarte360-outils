from clarte360_pip.framework.unsaved_guard import (
    mark_public_work_saved,
    public_has_unsaved_work,
    public_work_fingerprint,
    public_work_started,
)


def state_with_answer():
    return {
        "pip_state": {"answers": {"Q1": 3}, "index": 0},
        "onet_state": {},
        "feeling": {},
        "journey": "PIP_SEUL",
    }


def test_no_guard_before_work_starts():
    state = {"pip_state": {}, "onet_state": {}, "feeling": {}}
    assert public_work_started(state) is False
    assert public_has_unsaved_work(state) is False


def test_guard_activates_when_answer_exists():
    state = state_with_answer()
    assert public_work_started(state) is True
    assert public_has_unsaved_work(state) is True


def test_json_save_clears_guard_until_next_change():
    state = state_with_answer()
    mark_public_work_saved(state)
    assert public_has_unsaved_work(state) is False
    state["pip_state"]["answers"]["Q2"] = 5
    assert public_has_unsaved_work(state) is True


def test_volatile_navigation_is_not_part_of_fingerprint():
    state = state_with_answer()
    first = public_work_fingerprint(state)
    state["navigation_page"] = "contact"
    state["session_history"] = [{"at": "now"}]
    assert public_work_fingerprint(state) == first


def test_onet_answer_rearms_guard_after_save():
    state = {"pip_state": {}, "onet_state": {"answers": {"1": 2}}, "feeling": {}, "journey": "PIP_PUIS_ONET60"}
    mark_public_work_saved(state)
    assert public_has_unsaved_work(state) is False
    state["onet_state"]["answers"]["2"] = 4
    assert public_has_unsaved_work(state) is True
