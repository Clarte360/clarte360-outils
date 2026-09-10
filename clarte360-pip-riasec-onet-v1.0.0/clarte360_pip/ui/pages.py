from __future__ import annotations

import streamlit as st

from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.framework.contact import render_contact
from clarte360_pip.framework.persistence import snapshot_bytes, restore_snapshot
from clarte360_pip.scoring import score_pip
from clarte360_pip.journey import results_allowed, next_after_pip
from clarte360_pip.framework.rgpd import render_rgpd
from clarte360_pip.pip_data.loader import load_pip_bank
from clarte360_pip.pip_data.validation import assert_valid_bank
from clarte360_pip.questionnaire import QuestionnaireEngine, build_order


def render_home(launch: LaunchContext) -> None:
    st.title("PIP RIASEC Clarte360")
    st.caption("Profil d'Intérêts Professionnels — Livrable 1")
    st.markdown(f'<span class="clarte-mode">{launch.mode.value}</span>', unsafe_allow_html=True)
    uploaded=st.file_uploader("Reprendre une sauvegarde PIP", type=["json"])
    if uploaded is not None and st.button("Reprendre cette passation"):
        import json
        restore_snapshot(json.load(uploaded), st.session_state); st.rerun()
    st.markdown(
        """
<div class="clarte-box">
<b>Le PIP est un questionnaire francais complet et autonome.</b><br>
Il explore l'attraction pour des activites, situations et environnements professionnels selon le modele RIASEC.
</div>
""",
        unsafe_allow_html=True,
    )
    st.info("Le PIP utilise la banque pilote versionnée de 120 items. Aucun score ni aucune interprétation ne sont affichés pendant la passation.")
    if launch.mode is RunMode.ACCOMPANIMENT:
        st.markdown(f"**Action :** {launch.action_id}  ")
        st.markdown(f"**Beneficiaire :** {launch.beneficiary_id}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Commencer", type="primary", use_container_width=True):
            st.session_state.navigation_page = "rgpd"
            st.rerun()
    with c2:
        st.download_button(
            "Sauvegarder ma passation",
            data=snapshot_bytes(dict(st.session_state)),
            file_name="pip_clarte360_sauvegarde.json",
            mime="application/json",
            use_container_width=True,
        )


def render_pip_intro() -> None:
    st.subheader("Avant la passation PIP")
    st.success("Consentement Framework enregistré.")
    st.markdown("Le PIP explore votre **attraction / intérêt** pour des activités, situations et environnements professionnels. Il ne mesure ni compétence, ni aptitude, ni intelligence, ni personnalité.")
    st.info("120 propositions pilotes · réponses de 1 à 5 · aucun score ni interprétation pendant la passation.")
    journey=st.radio("Parcours", ["PIP_SEUL","PIP_PUIS_ONET60"], format_func=lambda x: "PIP seul (complet et autonome)" if x=="PIP_SEUL" else "PIP + comparaison facultative O*NET 60 en anglais")
    st.session_state.journey=journey
    if st.button("Démarrer le PIP", type="primary"):
        bank=load_pip_bank(); assert_valid_bank(bank)
        st.session_state.pip_state={"bank_version":bank["bank_version"],"order":build_order(bank,st.session_state.passation_id),"answers":{},"index":0}
        st.session_state.navigation_page="pip_questionnaire"; st.rerun()

def render_pip_questionnaire() -> None:
    bank=load_pip_bank(); assert_valid_bank(bank)
    ps=st.session_state.pip_state
    if not ps.get("order"):
        ps.update({"bank_version":bank["bank_version"],"order":build_order(bank,st.session_state.passation_id),"answers":{},"index":0})
    engine=QuestionnaireEngine(bank,ps["order"],ps["answers"],ps["index"])
    item=engine.current
    st.progress((engine.index+1)/engine.total, text=f"Question {engine.index+1} sur {engine.total}")
    block_names={"ACT":"Activités qui m'attirent","SIT":"Situations / problèmes","ENV":"Environnements"}
    st.caption(block_names[item["bloc"]])
    st.subheader(item["texte_fr"])
    options=list(range(1,6)); scale=bank["response_scale"]
    current=engine.answers.get(engine.current_id)
    choice=st.radio("Votre réponse", options, index=(current-1 if current else None), format_func=lambda x:f"{x} — {scale[str(x)]}", key=f"ans_{engine.current_id}")
    c1,c2=st.columns(2)
    with c1:
        if st.button("Précédent", disabled=engine.index==0, use_container_width=True):
            if choice is not None: engine.answer(choice)
            engine.previous(); ps["index"]=engine.index; st.rerun()
    with c2:
        label="Terminer la passation" if engine.index==engine.total-1 else "Suivant"
        if st.button(label, type="primary", disabled=choice is None, use_container_width=True):
            engine.answer(choice); ps["answers"]=engine.answers
            if engine.index==engine.total-1:
                ps["completed"]=engine.completed(); result=score_pip(bank,engine.answers); st.session_state.pip_scoring={"means":result.means,"indices":result.indices,"order":result.order,"exact_ties":result.exact_ties,"holland_code":result.holland_code,"complete":result.complete,"algorithm_version":result.algorithm_version}; st.session_state.navigation_page=next_after_pip(st.session_state.get("journey","PIP_SEUL"))
            else:
                engine.next(); ps["index"]=engine.index
            st.rerun()
    st.caption("Les dimensions et facettes associées aux questions ne sont jamais affichées pendant la passation.")

def render_pip_complete() -> None:
    st.success("Passation PIP terminée.")
    st.info("Le scoring déterministe a été calculé et conservé. La restitution bénéficiaire complète reste volontairement réservée au lot prévu.")

def render_onet_pending() -> None:
    st.success("Passation PIP terminée.")
    st.warning("Parcours O*NET choisi : aucun résultat PIP n’est affiché avant la fin de l’O*NET 60.")
    st.info("Le connecteur et la passation O*NET seront développés dans le lot dédié. Le verrou anti-influence est déjà actif.")

def render_results_gate() -> None:
    allowed=results_allowed(st.session_state.get("journey","PIP_SEUL"), bool(st.session_state.get("pip_state",{}).get("completed")), bool(st.session_state.get("onet_state",{}).get("completed")))
    if not allowed:
        st.error("Résultats verrouillés jusqu’à la fin du parcours prévu.")
        return
    render_pip_complete()


def render_timeout() -> None:
    st.warning("Session interrompue pour inactivite.")
    st.download_button(
        "Telecharger la sauvegarde de reprise",
        data=snapshot_bytes(dict(st.session_state)),
        file_name="pip_clarte360_reprise_timeout.json",
        mime="application/json",
        type="primary",
    )


def render_page(launch: LaunchContext) -> None:
    page = st.session_state.get("navigation_page", "accueil")
    if page == "accueil":
        render_home(launch)
    elif page == "rgpd":
        render_rgpd()
    elif page == "pip_intro":
        render_pip_intro()
    elif page == "pip_questionnaire":
        render_pip_questionnaire()
    elif page == "pip_complete":
        render_pip_complete()
    elif page == "pip_results_gate":
        render_results_gate()
    elif page == "onet_pending":
        render_onet_pending()
    elif page == "contact":
        render_contact()
    elif page == "timeout":
        render_timeout()
    else:
        st.error("Ecran indisponible.")
