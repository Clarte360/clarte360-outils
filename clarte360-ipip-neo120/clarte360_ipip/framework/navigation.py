from __future__ import annotations
import streamlit as st

VALID_PAGES = {"accueil", "passation", "rgpd", "mentions", "contact", "timeout"}


def go(page: str) -> None:
    if page not in VALID_PAGES:
        raise ValueError(f"Page inconnue: {page}")
    st.session_state.navigation_page = page
    st.rerun()
