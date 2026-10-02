from __future__ import annotations
import streamlit as st
from clarte360_ipip.framework.config import ASSETS_DIR
from clarte360_ipip.version import APP_VERSION, FRAMEWORK_VERSION


def render_sidebar(status: str | None = None) -> None:
    logo = ASSETS_DIR / "logo_clarte360.png"
    if logo.exists():
        st.sidebar.image(str(logo), width=125)
    st.sidebar.markdown("### Profil de fonctionnement professionnel")
    st.sidebar.caption("Mode ACCOMPAGNEMENT")
    if status:
        st.sidebar.caption(f"Statut : {status}")
    st.sidebar.markdown("---")
    if st.sidebar.button("Accueil", use_container_width=True):
        st.session_state.navigation_page = "accueil"; st.rerun()
    label = "Ma passation / Reprendre"
    if st.sidebar.button(label, use_container_width=True):
        st.session_state.navigation_page = "passation"; st.rerun()
    if st.sidebar.button("RGPD et confidentialité", use_container_width=True):
        st.session_state.navigation_page = "rgpd"; st.rerun()
    if st.sidebar.button("Mentions / informations", use_container_width=True):
        st.session_state.navigation_page = "mentions"; st.rerun()
    if st.sidebar.button("Contacter Clarté360", use_container_width=True):
        st.session_state.navigation_page = "contact"; st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Version {APP_VERSION} • Framework {FRAMEWORK_VERSION}")
