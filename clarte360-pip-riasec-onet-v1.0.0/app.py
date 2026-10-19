from __future__ import annotations

import streamlit as st

from clarte360_pip.framework.branding import apply_framework_css
from clarte360_pip.framework.config import APP_SHORT_NAME, LOGO_PATH
from clarte360_pip.framework.session import initialize_session, remember_current_page, touch_activity
from clarte360_pip.framework.persistence import restore_snapshot
from clarte360_pip.framework.server_store import SnapshotConflict
from clarte360_pip.framework.resume import restore_accompanied
from clarte360_pip.framework.public_access import enforce_public_verification
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
if not restore_accompanied(launch, st.session_state):
    st.error("Votre sauvegarde n'a pas pu être reprise. Vos réponses sont conservées : aucun nouveau questionnaire n'a été créé. Réessayez ou contactez votre accompagnateur.")
    if st.button("Réessayer la reprise", type="primary"):
        st.session_state.server_resume_checked = False
        st.rerun()
    st.stop()
if launch.mode is RunMode.PUBLIC:
    enforce_public_verification(st.session_state)
remember_current_page()
enforce_timeout()
if st.session_state.get("navigation_page") != "timeout":
    touch_activity("render")
render_sidebar(launch.mode.value)
try:
    render_page(launch)
except SnapshotConflict:
    st.error("Une sauvegarde plus récente ou une autre session existe. Fermez cet onglet et reprenez l'outil depuis votre espace. Aucune ancienne réponse n'a été remplacée.")
    st.stop()
render_browser_unsaved_guard(launch.mode is RunMode.PUBLIC and public_has_unsaved_work(st.session_state))
