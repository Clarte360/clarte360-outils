from __future__ import annotations
from datetime import datetime
import streamlit as st
from .config import RGPD_TEXT_VERSION

RGPD_TEXT = """
### Protection des données personnelles
Le PIP RIASEC Clarté360 explore les **intérêts professionnels**. Il ne prend aucune décision automatisée d’orientation et n’utilise aucune intelligence artificielle pour les questions, le scoring ou la restitution déterministe.

En accès public, vos coordonnées servent à **sécuriser votre accès, vous envoyer votre code et gérer votre passation**. L’autorisation de recevoir des informations ou offres Clarté360 est demandée séparément et reste facultative.

Si vous l’acceptez, les réponses et résultats de passation peuvent aussi alimenter les **travaux d’étude et de validation du PIP et de sa comparaison avec O*NET**, dans une base de recherche pseudonymisée séparée de vos coordonnées d’identification.
"""

def render_rgpd() -> None:
    st.subheader("Vos données, vos choix")
    st.markdown(RGPD_TEXT)
    accepted = st.checkbox("J’ai lu ces informations et j’accepte le traitement nécessaire à ma passation.", key="rgpd_checkbox")
    study = st.checkbox("J’accepte que mes réponses et résultats pseudonymisés soient utilisés pour les études et la validation méthodologique du PIP / O*NET.", key="study_checkbox")
    if st.button("Valider et continuer", type="primary", disabled=not accepted, use_container_width=True):
        now=datetime.now(); st.session_state.study_consent=bool(study)
        st.session_state.rgpd_acceptance={"consentement":True,"date":now.strftime("%Y-%m-%d"),"heure":now.strftime("%H:%M:%S"),"version_texte":RGPD_TEXT_VERSION,"study_consent":bool(study)}
        st.session_state.navigation_page="pip_intro"; st.rerun()
