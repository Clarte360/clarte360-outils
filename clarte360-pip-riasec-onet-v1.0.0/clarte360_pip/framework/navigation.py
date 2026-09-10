from __future__ import annotations

import streamlit as st

VALID_PAGES = {"accueil", "rgpd", "pip_intro", "pip_questionnaire", "pip_complete", "contact", "mentions", "timeout"}


def go(page: str) -> None:
    if page not in VALID_PAGES:
        raise ValueError(f"Page inconnue: {page}")
    st.session_state.navigation_page = page
    st.rerun()
