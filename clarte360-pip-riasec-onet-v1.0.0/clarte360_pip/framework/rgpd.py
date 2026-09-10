from __future__ import annotations

from datetime import datetime

import streamlit as st

from .config import RGPD_TEXT_VERSION

RGPD_TEXT = """
### Protection des donnees personnelles (RGPD)

Le PIP RIASEC Clarte360 est un outil d'exploration des interets professionnels. Les donnees necessaires a la passation sont limitees a ce qui est utile au parcours choisi et a sa tracabilite.

En mode **PUBLIC / ETUDE**, aucune action Clarte360 ni fiche beneficiaire de Gestion des actions n'est interrogee. Le rattachement a un dossier Clarte360 est reserve au mode **ACCOMPAGNEMENT** et sera assure par le connecteur securise prevu par le cahier des charges.

Le PIP ne realise aucune decision d'orientation automatisee et n'utilise aucune intelligence artificielle pour les questions, les reponses, le scoring, le ressenti ou les decisions deterministes.

Les durees de conservation, finalites detaillees et mecanismes definitifs de retrait seront consolides dans les lots qui mettent effectivement en service les stockages Public/Etude et Accompagnement.
"""


def render_rgpd() -> None:
    st.subheader("Protection des donnees personnelles")
    st.markdown(RGPD_TEXT)
    accepted = st.checkbox("J'ai lu les informations et j'accepte de poursuivre.", key="rgpd_checkbox")
    if st.button("Valider et continuer", type="primary", disabled=not accepted, use_container_width=True):
        now = datetime.now()
        st.session_state.rgpd_acceptance = {
            "consentement": True,
            "date": now.strftime("%Y-%m-%d"),
            "heure": now.strftime("%H:%M:%S"),
            "version_texte": RGPD_TEXT_VERSION,
        }
        st.session_state.navigation_page = "pip_intro"
        st.rerun()
