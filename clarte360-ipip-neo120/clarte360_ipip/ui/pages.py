from __future__ import annotations

import streamlit as st

from clarte360_ipip.framework.config import ASSETS_DIR
from clarte360_ipip.framework.contact import render_contact
from clarte360_ipip.framework.rgpd import NON_CLINICAL_NOTICE, render_rgpd_information


def render_header_logo() -> None:
    logo = ASSETS_DIR / "logo_clarte360.png"
    if logo.exists():
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.image(str(logo), use_container_width=True)


def render_home(*, reference_version: str, started: bool, information_current: bool) -> str | None:
    render_header_logo()
    st.title("Profil de fonctionnement professionnel")
    st.caption("Explorer mes tendances de fonctionnement")
    st.markdown(
        '<div class="clarte-hero"><b>Comment ai-je tendance à fonctionner ?</b><br/>'
        "Cet outil explore cinq grandes dimensions et 30 facettes afin de soutenir votre réflexion professionnelle. "
        "Il ne vous enferme pas dans un type et ne décide rien à votre place.</div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Ce que l'outil explore")
        st.write("• des tendances de fonctionnement\n\n• 5 grandes dimensions\n\n• 30 facettes\n\n• des repères à mettre en perspective avec votre parcours")
    with col2:
        st.markdown("#### Ce que l'outil n'est pas")
        st.write("• ni un diagnostic\n\n• ni une mesure d'intelligence\n\n• ni une aptitude\n\n• ni une sélection\n\n• ni une recommandation automatique de métier")

    st.markdown("#### Votre passation")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Affirmations", "120")
    m2.metric("Échelle", "1 à 5")
    m3.metric("Sauvegarde", "Automatique")
    m4.metric("Reprise", "Possible")
    st.caption("Durée indicative : environ 15 à 25 minutes selon votre rythme. Vous pouvez interrompre et reprendre votre passation.")

    st.info(NON_CLINICAL_NOTICE)
    st.write(
        "Vos résultats sont destinés à être discutés dans votre accompagnement et croisés avec votre expérience, "
        "vos valeurs, vos motivations, vos préférences, vos compétences et votre projet professionnel."
    )
    st.caption(f"Référentiel actif : {reference_version}")

    if started:
        st.success("Votre passation a déjà commencé. Votre progression enregistrée est conservée.")
        if information_current:
            if st.button("Reprendre ma passation", type="primary", use_container_width=True):
                return "passation"
        else:
            if st.button("Lire les informations obligatoires avant de reprendre", type="primary", use_container_width=True):
                return "information"
    else:
        if information_current:
            if st.button("Commencer ma passation", type="primary", use_container_width=True):
                return "passation"
        else:
            if st.button("Lire les informations et poursuivre", type="primary", use_container_width=True):
                return "information"
    return None


def render_mentions(reference_version: str) -> None:
    st.subheader("Mentions / informations")
    st.markdown("**Clarté360 — Profil de fonctionnement professionnel**")
    st.write("Finalité : explorer des tendances de fonctionnement professionnel afin de soutenir la réflexion et le dialogue dans l'accompagnement.")
    st.write("Base scientifique : Johnson IPIP-NEO-120 / International Personality Item Pool. Adaptation française Clarté360.")
    st.write("Les items et échelles IPIP sont issus d'une ressource publique. L'adaptation française Clarté360 n'est pas présentée comme une validation psychométrique française indépendante.")
    st.write("L'outil ne constitue ni un diagnostic, ni une aptitude, ni une mesure d'intelligence, ni une sélection, ni une recommandation automatique de métier.")
    st.write("La facette O6 « Ouverture aux conventions » est une adaptation Clarté360 non politique ; elle ne doit pas être considérée comme strictement équivalente à l'O6 Johnson original.")
    st.caption(f"Référentiel IPIP actif : {reference_version}")


def render_auxiliary_page(page: str, reference_version: str) -> bool:
    if page == "contact":
        render_contact(); return True
    if page == "rgpd":
        render_rgpd_information(reference_version=reference_version); return True
    if page == "mentions":
        render_mentions(reference_version); return True
    if page == "timeout":
        st.warning("Votre session a expiré. Votre progression enregistrée côté serveur est conservée. Rouvrez l'outil depuis Gestion des Actions pour reprendre.")
        return True
    return False
