from __future__ import annotations

import json
import streamlit as st

from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.framework.config import LOGO_PATH, ASSETS_DIR
from clarte360_pip.framework.contact import render_contact
from clarte360_pip.framework.persistence import snapshot_bytes, restore_snapshot
from clarte360_pip.scoring import score_pip
from clarte360_pip.journey import results_allowed, next_after_pip
from clarte360_pip.framework.rgpd import render_rgpd
from clarte360_pip.pip_data.loader import load_pip_bank
from clarte360_pip.pip_data.validation import assert_valid_bank
from clarte360_pip.questionnaire import QuestionnaireEngine, build_order
from clarte360_pip.feeling import QUESTIONS, build_feeling_record
from clarte360_pip.framework.server_store import save_accompanied_snapshot
from clarte360_pip.connectors.gestion_actions import GestionActionsPort



def _save_if_accompanied() -> None:
    launch = st.session_state.get("launch_context")
    if not launch or launch.mode is not RunMode.ACCOMPANIMENT:
        return
    save_accompanied_snapshot(dict(st.session_state), launch.action_id, launch.beneficiary_id, launch.prescription_id)


def _publish_if_accompanied(event_type: str) -> None:
    launch = st.session_state.get("launch_context")
    if not launch or launch.mode is not RunMode.ACCOMPANIMENT:
        return
    port = GestionActionsPort(None)
    port.publish_event(event_type, {
        "beneficiary_id": launch.beneficiary_id,
        "action_id": launch.action_id,
        "participant_id": launch.participant_id,
        "prescription_id": launch.prescription_id,
        "passation_id": st.session_state.get("passation_id"),
        "app_version": st.session_state.get("app_version"),
    })

DIMENSION_LABELS = {
    "R": "Réaliste — agir concrètement sur le réel",
    "I": "Investigateur — comprendre, analyser, rechercher",
    "A": "Artistique — créer, imaginer, exprimer",
    "S": "Social — aider, transmettre, accompagner",
    "E": "Entreprenant — initier, convaincre, décider",
    "C": "Conventionnel — organiser, fiabiliser, suivre",
}


def _render_logo() -> None:
    logo = ASSETS_DIR / "logo_clarte360.png"
    if logo.exists():
        st.image(str(logo), width=230)


def _restore_uploaded(uploaded) -> None:
    payload = json.load(uploaded)
    restore_snapshot(payload, st.session_state)


def render_home(launch: LaunchContext) -> None:
    _render_logo()
    st.title("PIP RIASEC Clarté360")
    st.caption("Profil d’Intérêts Professionnels")
    st.markdown(f'<span class="clarte-mode">{launch.mode.value}</span>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="clarte-box">
<b>Le PIP est un questionnaire français complet et autonome.</b><br>
Il explore l’attraction pour des activités, situations et environnements professionnels selon le modèle RIASEC.
</div>
""",
        unsafe_allow_html=True,
    )
    st.info("Banque pilote : 120 items. Aucun score ni aucune interprétation ne sont affichés pendant la passation.")

    if launch.mode is RunMode.PUBLIC:
        st.markdown("### Reprendre une passation publique")
        uploaded = st.file_uploader("Choisissez votre fichier JSON de sauvegarde", type=["json"], key="resume_json")
        if uploaded is not None and st.button("Reprendre cette passation", use_container_width=True):
            try:
                _restore_uploaded(uploaded)
                st.success("Sauvegarde reconnue. Reprise de la passation…")
                st.rerun()
            except Exception as exc:
                st.error(f"Sauvegarde incompatible : {exc}")
        st.caption("Le mode accompagné utilise l’identité permanente de l’Espace bénéficiaire Clarté360. Aucun second compte PIP n’est créé.")
    else:
        st.success("Accès bénéficiaire Clarté360 reconnu.")
        if st.session_state.get("server_resume_restored"):
            st.info("Votre passation précédente a été retrouvée automatiquement. Vous pouvez la poursuivre là où vous l’aviez laissée.")
        if st.session_state.get("server_resume_error"):
            st.warning("La reprise automatique n’a pas pu être chargée. Votre accès reste valide ; contactez Clarté360 si nécessaire.")
        st.markdown(f"**Action :** {launch.action_id}  ")
        st.markdown(f"**Bénéficiaire :** {launch.beneficiary_id}")
        st.caption("Votre progression est sauvegardée automatiquement sur le serveur Clarté360.")
        if not st.session_state.get("consulted_event_published"):
            _publish_if_accompanied("CONSULTE")
            st.session_state.consulted_event_published = True

    if st.button("Commencer une nouvelle passation", type="primary", use_container_width=True):
        st.session_state.navigation_page = "rgpd"
        st.rerun()


def render_pip_intro() -> None:
    _render_logo()
    st.subheader("Avant la passation PIP")
    st.success("Consentement enregistré.")
    st.markdown("Le PIP explore votre **attraction / intérêt**. Il ne mesure ni compétence, ni aptitude, ni intelligence, ni personnalité.")
    st.info("120 propositions pilotes · réponses de 1 à 5 · exemples concrets pour limiter les interprétations ambiguës · aucun score pendant la passation.")
    journey = st.radio(
        "Parcours",
        ["PIP_SEUL", "PIP_PUIS_ONET60"],
        format_func=lambda x: "PIP seul (complet et autonome)" if x == "PIP_SEUL" else "PIP + comparaison facultative O*NET 60 en anglais",
    )
    st.session_state.journey = journey
    if st.button("Démarrer le PIP", type="primary", use_container_width=True):
        bank = load_pip_bank(); assert_valid_bank(bank)
        st.session_state.pip_state = {"bank_version": bank["bank_version"], "order": build_order(bank, st.session_state.passation_id), "answers": {}, "index": 0}
        st.session_state.navigation_page = "pip_questionnaire"
        _save_if_accompanied(); _publish_if_accompanied("EN_COURS")
        st.rerun()


def render_pip_questionnaire() -> None:
    bank = load_pip_bank(); assert_valid_bank(bank)
    ps = st.session_state.pip_state
    if not ps.get("order"):
        ps.update({"bank_version": bank["bank_version"], "order": build_order(bank, st.session_state.passation_id), "answers": {}, "index": 0})
    engine = QuestionnaireEngine(bank, ps["order"], ps["answers"], ps["index"])
    item = engine.current
    st.progress((engine.index + 1) / engine.total, text=f"Question {engine.index + 1} sur {engine.total}")
    block_names = {"ACT": "Activités qui m’attirent", "SIT": "Situations / problèmes", "ENV": "Environnements"}
    st.caption(block_names[item["bloc"]])
    st.subheader(item["texte_fr"])
    if item.get("exemple_concret"):
        st.markdown(f'<div class="clarte-example"><b>Exemple concret :</b> {item["exemple_concret"]}</div>', unsafe_allow_html=True)
    options = list(range(1, 6)); scale = bank["response_scale"]
    current = engine.answers.get(engine.current_id)
    choice = st.radio("Votre réponse", options, index=(current - 1 if current else None), format_func=lambda x: f"{x} — {scale[str(x)]}", key=f"ans_{engine.current_id}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Précédent", disabled=engine.index == 0, use_container_width=True):
            if choice is not None: engine.answer(choice)
            ps["answers"] = engine.answers; engine.previous(); ps["index"] = engine.index; _save_if_accompanied(); st.rerun()
    with c2:
        label = "Terminer la passation" if engine.index == engine.total - 1 else "Suivant"
        if st.button(label, type="primary", disabled=choice is None, use_container_width=True):
            engine.answer(choice); ps["answers"] = engine.answers
            if engine.index == engine.total - 1:
                ps["completed"] = engine.completed()
                result = score_pip(bank, engine.answers)
                st.session_state.pip_scoring = {"means": result.means, "indices": result.indices, "order": result.order, "exact_ties": result.exact_ties, "holland_code": result.holland_code, "complete": result.complete, "algorithm_version": result.algorithm_version}
                st.session_state.navigation_page = next_after_pip(st.session_state.get("journey", "PIP_SEUL"))
                _save_if_accompanied()
                if st.session_state.get("journey", "PIP_SEUL") == "PIP_SEUL":
                    _publish_if_accompanied("TERMINE")
                else:
                    _publish_if_accompanied("EN_COURS")
            else:
                engine.next(); ps["index"] = engine.index; _save_if_accompanied()
            st.rerun()

    # Capture also the currently selected answer before exporting a pause snapshot.
    if choice is not None:
        engine.answer(choice)
        ps["answers"] = engine.answers
    st.markdown("---")
    launch = st.session_state.get("launch_context")
    if launch and launch.mode is RunMode.PUBLIC:
        st.download_button(
            "💾 Sauvegarder et quitter plus tard (JSON)",
            data=snapshot_bytes(dict(st.session_state)),
            file_name="pip_clarte360_sauvegarde.json",
            mime="application/json",
            use_container_width=True,
        )
        st.caption("Votre sauvegarde permet de reprendre au même endroit. Aucun résultat intermédiaire n’est exporté.")
    else:
        _save_if_accompanied()
        st.info("Sauvegarde automatique Clarté360 active. Vous pourrez reprendre depuis votre espace bénéficiaire.")


def render_pip_results() -> None:
    scoring = st.session_state.get("pip_scoring", {})
    if not scoring or not scoring.get("complete"):
        st.error("La restitution nécessite une passation PIP complète.")
        return
    _render_logo()
    st.success("Passation PIP terminée — voici votre profil d’intérêts.")
    st.caption("Ces résultats décrivent des préférences relatives. Ils ne mesurent ni vos compétences ni votre capacité à exercer un métier et ne constituent pas une prescription.")
    indices = scoring["indices"]
    order = scoring["order"]
    for d in order:
        st.markdown(f"**{d} — {DIMENSION_LABELS[d]}**")
        st.progress(max(0.0, min(1.0, float(indices[d]) / 100.0)), text=f"Indice {float(indices[d]):.0f} / 100")
    if scoring.get("holland_code"):
        st.info(f"Code de synthèse Holland : **{scoring['holland_code']}**. Il résume uniquement l’ordre relatif des trois dimensions dominantes lorsqu’il est non ambigu.")
    else:
        st.info("Aucun code Holland à trois lettres n’est forcé : des égalités ou une proximité de scores rendent une synthèse unique injustifiée.")
    if st.button("Continuer vers mon ressenti", type="primary", use_container_width=True):
        st.session_state.navigation_page = "feeling"; st.rerun()


def render_feeling() -> None:
    _render_logo()
    st.subheader("Votre ressenti sur le profil")
    st.caption("Ce questionnaire fermé sert à comparer votre ressenti au résultat sans modifier le scoring PIP.")
    answers = {}
    scale = [1, 2, 3, 4, 5]
    labels = {1:"Pas du tout",2:"Plutôt non",3:"Partagé(e)",4:"Plutôt oui",5:"Tout à fait"}
    for key in ("global", "dominants", "nuances", "useful"):
        q = QUESTIONS[key]
        answers[key] = st.radio(q["text"], scale, index=None, format_func=lambda x: f"{x} — {labels[x]}", key=f"feel_{key}")
    answers["over"] = st.selectbox(QUESTIONS["over"]["text"], ["Aucune", "R", "I", "A", "S", "E", "C"], key="feel_over")
    answers["under"] = st.selectbox(QUESTIONS["under"]["text"], ["Aucune", "R", "I", "A", "S", "E", "C"], key="feel_under")
    answers["dialogue"] = st.radio(QUESTIONS["dialogue"]["text"], ["NON", "OUI"], index=None, key="feel_dialogue")
    required = [answers[k] for k in ("global","dominants","nuances","useful","dialogue")]
    if st.button("Valider mon ressenti", type="primary", disabled=any(v is None for v in required), use_container_width=True):
        st.session_state.feeling = build_feeling_record(answers, st.session_state.get("journey", "PIP_SEUL"), "PIP-RPT-L1-MIN")
        st.session_state.navigation_page = "finished"; st.rerun()


def render_finished() -> None:
    _render_logo()
    st.success("Votre parcours PIP est terminé.")
    launch = st.session_state.get("launch_context")
    if launch and launch.mode is RunMode.PUBLIC:
        st.markdown("Votre profil et votre ressenti ont été enregistrés dans la session en cours.")
        st.download_button("Télécharger ma sauvegarde finale (JSON)", data=snapshot_bytes(dict(st.session_state)), file_name="pip_clarte360_final.json", mime="application/json", use_container_width=True)
    else:
        _save_if_accompanied()
        st.markdown("Votre profil et votre ressenti ont été enregistrés dans votre parcours Clarté360.")


def render_onet_pending() -> None:
    st.success("Passation PIP terminée.")
    st.warning("Parcours O*NET choisi : aucun résultat PIP n’est affiché avant la fin de l’O*NET 60.")
    st.info("Le connecteur et la passation O*NET restent dans le lot dédié. Le verrou anti-influence est actif.")


def render_results_gate() -> None:
    allowed = results_allowed(st.session_state.get("journey", "PIP_SEUL"), bool(st.session_state.get("pip_state", {}).get("completed")), bool(st.session_state.get("onet_state", {}).get("completed")))
    if not allowed:
        st.error("Résultats verrouillés jusqu’à la fin du parcours prévu.")
        return
    render_pip_results()


def render_timeout() -> None:
    st.warning("Session interrompue pour inactivité.")
    st.download_button("Télécharger la sauvegarde de reprise", data=snapshot_bytes(dict(st.session_state)), file_name="pip_clarte360_reprise_timeout.json", mime="application/json", type="primary")


def render_page(launch: LaunchContext) -> None:
    page = st.session_state.get("navigation_page", "accueil")
    if page == "accueil": render_home(launch)
    elif page == "rgpd": render_rgpd()
    elif page == "pip_intro": render_pip_intro()
    elif page == "pip_questionnaire": render_pip_questionnaire()
    elif page in ("pip_complete", "pip_results_gate"): render_results_gate()
    elif page == "feeling": render_feeling()
    elif page == "finished": render_finished()
    elif page == "onet_pending": render_onet_pending()
    elif page == "contact": render_contact()
    elif page == "timeout": render_timeout()
    else: st.error("Écran indisponible.")
