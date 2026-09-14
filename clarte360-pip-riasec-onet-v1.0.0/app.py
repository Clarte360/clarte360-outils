from __future__ import annotations

import streamlit as st

from clarte360_pip.framework.branding import apply_framework_css
from clarte360_pip.framework.config import APP_SHORT_NAME, LOGO_PATH
from clarte360_pip.framework.session import initialize_session, touch_activity
from clarte360_pip.framework.persistence import restore_snapshot
from clarte360_pip.framework.server_store import load_latest_accompanied_snapshot
from clarte360_pip.framework.unsaved_guard import public_has_unsaved_work, render_browser_unsaved_guard
from clarte360_pip.domain import RunMode
from clarte360_pip.framework.timeout import enforce_timeout
from clarte360_pip.ui.entry import resolve_launch_context
from clarte360_pip.ui.pages import render_page
from clarte360_pip.ui.sidebar import render_sidebar

st.set_page_config(
    page_title=APP_SHORT_NAME,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "C360",
    layout="centered",
)
apply_framework_css()

try:
    launch = resolve_launch_context()
except ValueError as exc:
    st.error(str(exc))
    st.stop()

initialize_session(launch)
if launch.mode is RunMode.ACCOMPANIMENT and not st.session_state.get("server_resume_checked"):
    st.session_state.server_resume_checked = True
    try:
        saved = load_latest_accompanied_snapshot(launch.action_id, launch.beneficiary_id, launch.prescription_id)
        if saved:
            restore_snapshot(saved, st.session_state)
            st.session_state.launch_context = launch
            st.session_state.server_resume_restored = True
    except Exception as exc:
        st.session_state.server_resume_error = str(exc)
enforce_timeout()
touch_activity("render")
render_sidebar(launch.mode.value)
render_page(launch)
render_browser_unsaved_guard(launch.mode is RunMode.PUBLIC and public_has_unsaved_work(st.session_state))
