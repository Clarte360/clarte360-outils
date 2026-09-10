from __future__ import annotations

import streamlit as st

from .config import CLARTE360_LEGAL


def render_contact() -> None:
    st.subheader("Contacter Clarte360")
    st.markdown(
        f"**{CLARTE360_LEGAL['raison_sociale']}**  \n"
        f"{CLARTE360_LEGAL['adresse']} - {CLARTE360_LEGAL['code_postal_ville']}  \n"
        f"Telephone : {CLARTE360_LEGAL['telephone']}  \n"
        f"Email : {CLARTE360_LEGAL['email']}  \n"
        f"Web : {CLARTE360_LEGAL['web']}"
    )
