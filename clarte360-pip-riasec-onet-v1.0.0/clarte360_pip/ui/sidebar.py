from __future__ import annotations

import streamlit as st

from clarte360_pip.framework.config import ASSETS_DIR
from clarte360_pip.framework.persistence import decode_snapshot_bytes, restore_snapshot
from clarte360_pip.framework.unsaved_guard import mark_public_work_saved
from clarte360_pip.version import APP_VERSION, BUILD_INCREMENT, FRAMEWORK_VERSION


def render_sidebar(mode_label: str) -> None:
    logo = ASSETS_DIR / "logo_clarte360.png"
    if logo.exists():
        st.sidebar.image(str(logo), width=120)
    st.sidebar.markdown("**[www.clarte360.com](https://www.clarte360.com)**")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Navigation")
    st.sidebar.markdown(f"**Mode : {mode_label}**")
    if st.sidebar.button("Accueil", use_container_width=True):
        st.session_state.navigation_page = "accueil"; st.rerun()
    if st.sidebar.button("RGPD et mentions", use_container_width=True):
        st.session_state.navigation_page = "rgpd"; st.rerun()
    if st.sidebar.button("Contacter Clarté360", use_container_width=True):
        st.session_state.navigation_page = "contact"; st.rerun()

    if mode_label == "PUBLIC":
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Reprendre ma passation")
        st.sidebar.caption("Vous avez déjà une sauvegarde PIP ? Chargez-la ici.")
        uploaded = st.sidebar.file_uploader("Sauvegarde JSON", type=["json"], key="sidebar_resume_json", label_visibility="collapsed")
        if uploaded is not None and st.sidebar.button("Reprendre le fichier JSON", use_container_width=True):
            try:
                payload = decode_snapshot_bytes(uploaded.getvalue())
                restore_snapshot(payload, st.session_state)
                mark_public_work_saved(st.session_state)
                if not st.session_state.get("public_access_verified"):
                    raise ValueError("La sauvegarde ne contient pas d'accès public vérifié.")
                st.sidebar.success("Sauvegarde reconnue."); st.rerun()
            except Exception as exc:
                st.sidebar.error(f"Sauvegarde incompatible : {exc}")

    st.sidebar.markdown("---")
    st.sidebar.caption(f"App {APP_VERSION} | {BUILD_INCREMENT} | Framework {FRAMEWORK_VERSION}")
