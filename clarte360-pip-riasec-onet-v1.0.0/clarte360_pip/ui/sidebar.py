from __future__ import annotations

import streamlit as st

from clarte360_pip.version import APP_VERSION, BUILD_INCREMENT, FRAMEWORK_VERSION


def render_sidebar(mode_label: str) -> None:
    st.sidebar.markdown("### Navigation")
    st.sidebar.markdown(f"**Mode : {mode_label}**")
    if st.sidebar.button("Accueil", use_container_width=True):
        st.session_state.navigation_page = "accueil"
        st.rerun()
    if st.sidebar.button("RGPD et mentions", use_container_width=True):
        st.session_state.navigation_page = "rgpd"
        st.rerun()
    if st.sidebar.button("Contacter Clarte360", use_container_width=True):
        st.session_state.navigation_page = "contact"
        st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.caption(f"App {APP_VERSION} | {BUILD_INCREMENT} | Framework {FRAMEWORK_VERSION}")
