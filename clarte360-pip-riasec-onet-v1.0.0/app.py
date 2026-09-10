from __future__ import annotations

import streamlit as st

from clarte360_pip.framework.branding import apply_framework_css
from clarte360_pip.framework.config import APP_SHORT_NAME, LOGO_PATH
from clarte360_pip.framework.session import initialize_session, touch_activity
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
enforce_timeout()
touch_activity("render")
render_sidebar(launch.mode.value)
render_page(launch)
