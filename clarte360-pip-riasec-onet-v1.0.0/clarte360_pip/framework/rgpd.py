from __future__ import annotations
from datetime import datetime
from .config import RGPD_TEXT_VERSION

RGPD_TEXT = """
### Protection des données personnelles
Le PIP RIASEC Clarté360 explore les **intérêts professionnels**. Il ne prend aucune décision automatisée d’orientation et n’utilise aucune intelligence artificielle pour les questions, le scoring ou la restitution déterministe.

**Accès public.** Les données indispensables à l’ouverture et à la sécurisation de l’accès sont : **prénom, nom, téléphone et e-mail**. La fonction, l’entreprise et les centres d’intérêt Clarté360 sont facultatifs. Ils permettent, si vous choisissez de les renseigner, de mieux qualifier votre demande et les services susceptibles de vous intéresser.

Le choix de centres d’intérêt ne vaut pas consentement à la prospection. L’autorisation de recevoir des actualités, ressources ou offres Clarté360 est demandée dans une **case séparée et facultative**. Vous pouvez ne pas la cocher et accéder au PIP dans les mêmes conditions.

**Études PIP / O*NET.** Avec votre accord séparé, vos réponses, scores, ressenti et données techniques utiles à la validation méthodologique peuvent alimenter une **base d’étude pseudonymisée**, séparée de vos coordonnées d’identification. Les données PIP et O*NET y restent identifiables comme deux instruments distincts. Si O*NET est choisi après consultation des résultats PIP, cette chronologie est enregistrée afin de ne pas confondre ce parcours avec un parcours sans influence préalable.

**O*NET Interest Profiler.** O*NET est un outil américain distinct du PIP Clarté360. La version proposée comporte **60 activités en anglais** et utilise le service officiel O*NET Web Services. Les réponses et résultats O*NET sont conservés séparément des scores PIP ; leur rapprochement éventuel est descriptif et ne constitue pas une décision d’orientation automatique.

Les données sont conservées dans les espaces techniques Clarté360 nécessaires au service et aux finalités auxquelles vous avez consenti. Vous pouvez exercer vos droits d’accès, rectification, opposition ou effacement en contactant Clarté360 via la rubrique **Contacter Clarté360**. Les durées de conservation et règles de gestion pourront être administrées dans le futur module central Gestion des actions / Contacts Clarté360.
"""


def rgpd_is_current(state) -> bool:
    acceptance = state.get("rgpd_acceptance") or {}
    return bool(
        isinstance(acceptance, dict)
        and acceptance.get("consentement") is True
        and acceptance.get("version_texte") == RGPD_TEXT_VERSION
    )


def _return_page(st) -> str:
    target = st.session_state.get("rgpd_return_page") or st.session_state.get("last_useful_page") or "accueil"
    if target in {"rgpd", "timeout", "contact"}:
        target = "accueil"
    return target


def render_rgpd() -> None:
    import streamlit as st
    st.subheader("Vos données, vos choix")
    st.markdown(RGPD_TEXT)
    st.caption(f"Version de l'information RGPD : {RGPD_TEXT_VERSION}")

    if rgpd_is_current(st.session_state):
        acceptance = st.session_state.get("rgpd_acceptance") or {}
        st.success(
            "Vous avez déjà validé cette version des informations RGPD. "
            "Aucun nouveau consentement n'est demandé."
        )
        st.caption(
            f"Consentement enregistré le {acceptance.get('date', '—')} à {acceptance.get('heure', '—')} · "
            f"Étude pseudonymisée : {'oui' if acceptance.get('study_consent') else 'non'}"
        )
        if st.button("Retour à ma passation", type="primary", use_container_width=True):
            st.session_state.navigation_page = _return_page(st)
            st.rerun()
        return

    accepted = st.checkbox(
        "J’ai lu ces informations et j’accepte le traitement nécessaire à ma passation.",
        key="rgpd_checkbox",
    )
    study = st.checkbox(
        "J’accepte que mes réponses et résultats pseudonymisés soient utilisés pour les études et la validation méthodologique du PIP / O*NET.",
        key="study_checkbox",
        value=bool(st.session_state.get("study_consent", False)),
    )
    if st.button("Valider et continuer", type="primary", disabled=not accepted, use_container_width=True):
        now = datetime.now()
        st.session_state.study_consent = bool(study)
        st.session_state.rgpd_acceptance = {
            "consentement": True,
            "date": now.strftime("%Y-%m-%d"),
            "heure": now.strftime("%H:%M:%S"),
            "version_texte": RGPD_TEXT_VERSION,
            "study_consent": bool(study),
        }
        st.session_state.navigation_page = _return_page(st)
        st.rerun()
