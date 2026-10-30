from __future__ import annotations

from clarte360_cp.framework.navigation import set_page
from clarte360_cp.framework.session import reconcile_session_state
from .helpers import context


def test_navigation_changes_page_only():
    state={"navigation_page":"home","business_validation":False}
    set_page(state,"timeout")
    assert state["navigation_page"]=="timeout"
    assert state["business_validation"] is False


def test_navigation_rejects_unknown_page():
    state={}
    try:
        set_page(state,"validate_everything")
        ok=False
    except ValueError:
        ok=True
    assert ok


def test_session_reconciles_to_current_signed_case_without_cross_case_mix():
    old=context(beneficiary="B1",action="A1",prescription="P1",actor="U1")
    new=context(beneficiary="B2",action="A2",prescription="P2",actor="U2")
    state={"launch_context":old,"case_id":"OLD","case_row_version":9,"navigation_page":"home"}
    reconcile_session_state(state,new,"NEW",1)
    assert state["launch_context"].prescription_id=="P2"
    assert state["case_id"]=="NEW"
    assert state["case_row_version"]==1
