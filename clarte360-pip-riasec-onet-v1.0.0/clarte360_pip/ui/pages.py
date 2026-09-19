from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4
import streamlit as st

from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.framework.config import LOGO_PATH, ASSETS_DIR, RGPD_TEXT_VERSION, load_smtp_settings, load_onet_settings
from clarte360_pip.framework.contact import render_contact
from clarte360_pip.framework.persistence import snapshot_bytes, restore_snapshot, decode_snapshot_bytes, infer_resume_page
from clarte360_pip.framework.unsaved_guard import mark_public_work_saved
from clarte360_pip.scoring import score_pip
from clarte360_pip.journey import results_allowed, next_after_pip
from clarte360_pip.framework.rgpd import render_rgpd, rgpd_is_current
from clarte360_pip.pip_data.loader import load_pip_bank
from clarte360_pip.pip_data.validation import assert_valid_bank
from clarte360_pip.questionnaire import QuestionnaireEngine, build_order
from clarte360_pip.feeling import QUESTIONS, build_feeling_record
from clarte360_pip.framework.server_store import save_accompanied_snapshot
from clarte360_pip.connectors.gestion_actions import GestionActionsPort, persist_report_document
from clarte360_pip.connectors.onet import OnetPort, OnetApiError, normalize_onet_results, ONET_INSTRUMENT, ONET_API_VERSION, ONET_LANGUAGE
from clarte360_pip.framework.public_access import (validate_public_identity, validated_public_identity, issue_public_code, verify_public_code, save_public_lead, save_public_study_record)
from clarte360_pip.reporting import build_pip_report_pdf, build_onet_report_pdf, PIP_REPORT_VERSION, ONET_REPORT_VERSION, REPORT_VERSION
from clarte360_pip.pdf_preview import pdf_pages_as_png
from clarte360_pip.version import APP_VERSION



def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _public_contact_payload() -> dict:
    identity = dict(st.session_state.get("public_identity") or {})
    interests = list(st.session_state.get("public_interests") or [])
    if "PIP-RIASEC" not in interests:
        interests.append("PIP-RIASEC")
    acceptance = dict(st.session_state.get("rgpd_acceptance") or {})
    return {
        "source": "PIP_PUBLIC",
        "first_name": identity.get("first_name"),
        "last_name": identity.get("last_name"),
        "email": identity.get("email"),
        "phone": identity.get("phone"),
        "job_title": identity.get("job_title"),
        "company": identity.get("company"),
        "marketing_opt_in": bool(st.session_state.get("public_marketing_opt_in")),
        "rgpd_text_version": acceptance.get("version_texte") or RGPD_TEXT_VERSION,
        "interests": interests,
    }


def _publish_public_contact_event(event_type: str, extra: dict | None = None) -> None:
    launch = st.session_state.get("launch_context")
    if not launch or launch.mode is not RunMode.PUBLIC:
        return
    payload = _public_contact_payload()
    if extra:
        payload.update(extra)
    GestionActionsPort(None).publish_event(event_type, payload)


def _accompanied_final_payload(report_documents: list[dict]) -> dict:
    launch = st.session_state.get("launch_context")
    pip = dict(st.session_state.get("pip_scoring") or {})
    ps = dict(st.session_state.get("pip_state") or {})
    onet = dict(st.session_state.get("onet_state") or {})
    onet_rows = list(onet.get("results") or []) if onet.get("completed") else []
    onet_ranked = [
        {"rank": i + 1, "code": row.get("code"), "title": row.get("title"), "score": row.get("score")}
        for i, row in enumerate(onet_rows)
    ]
    return {
        "beneficiary_id": launch.beneficiary_id,
        "action_id": launch.action_id,
        "participant_id": launch.participant_id,
        "prescription_id": launch.prescription_id,
        "passation_id": st.session_state.get("passation_id"),
        "completed_at": st.session_state.get("completed_at"),
        "app_version": APP_VERSION,
        "pip": {
            "bank_version": ps.get("bank_version"),
            "scoring_version": pip.get("algorithm_version"),
            "report_version": PIP_REPORT_VERSION,
            "scores": pip.get("indices") or {},
            "ranking": pip.get("order") or [],
            "holland_code": pip.get("holland_code"),
            "exact_ties": pip.get("exact_ties") or [],
        },
        "onet": {
            "completed": bool(onet.get("completed")),
            "instrument": onet.get("instrument"),
            "api_version": onet.get("api_version"),
            "selected_timing": onet.get("selected_timing") or st.session_state.get("onet_selected_timing"),
            "ranking": onet_ranked,
            "report_version": ONET_REPORT_VERSION if onet.get("completed") else None,
        },
        "feeling": dict(st.session_state.get("feeling") or {}),
        "documents": report_documents,
    }


def _save_if_accompanied() -> None:
    launch = st.session_state.get("launch_context")
    if not launch or launch.mode is not RunMode.ACCOMPANIMENT:
        return
    save_accompanied_snapshot(dict(st.session_state), launch.action_id, launch.beneficiary_id, launch.prescription_id)


def _publish_if_accompanied(event_type: str) -> None:
    launch = st.session_state.get("launch_context")
    if not launch or launch.mode is not RunMode.ACCOMPANIMENT:
        return
    payload = {
        "beneficiary_id": launch.beneficiary_id,
        "action_id": launch.action_id,
        "participant_id": launch.participant_id,
        "prescription_id": launch.prescription_id,
        "passation_id": st.session_state.get("passation_id"),
        "app_version": APP_VERSION,
    }
    GestionActionsPort(None).publish_event(event_type, payload)

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
    st.markdown("# Découvrez ce qui vous attire vraiment dans le travail")
    st.markdown("### Votre Profil d’Intérêts Professionnels RIASEC Clarté360")
    st.markdown("""
<div class="clarte-hero">
<b>Le RIASEC, c’est une boussole pour mieux comprendre vos préférences professionnelles.</b><br><br>
Le modèle de Holland distingue six grandes familles d’intérêts : <b>Réaliste, Investigateur, Artistique, Social, Entreprenant et Conventionnel</b>.
Le PIP Clarté360 explore, au travers de 72 activités professionnelles, les activités, situations et environnements qui vous attirent le plus — et ceux qui vous attirent moins.
</div>
""", unsafe_allow_html=True)
    st.markdown("**À l’issue du questionnaire :** découvrez vos six dimensions RIASEC et, lorsque les résultats le permettent, votre code de synthèse Holland. Ce profil n’est ni un test de compétences ni un verdict : il éclaire vos préférences et vos choix professionnels.")
    st.markdown('<div class="clarte-stats"><b>72 activités</b> &nbsp; • &nbsp; <b>≈ 10–15 min</b> &nbsp; • &nbsp; <b>Résultat personnel</b> &nbsp; • &nbsp; <b>Sauvegarde possible</b></div>', unsafe_allow_html=True)

    if launch.mode is RunMode.ACCOMPANIMENT:
        st.success("Accès bénéficiaire Clarté360 reconnu.")
        if st.session_state.get("server_resume_restored"): st.info("Votre passation précédente a été retrouvée automatiquement.")
        st.markdown(f"**Bénéficiaire :** {launch.beneficiary_display_name}  \n**Action :** {launch.action_display_label}")
        st.caption("Cet outil vous a été adressé depuis votre parcours Clarté360. Votre progression est sauvegardée automatiquement.")
        if not st.session_state.get("consulted_event_published"):
            _publish_if_accompanied("CONSULTE"); st.session_state.consulted_event_published=True
        if st.button("Commencer / reprendre mon PIP", type="primary", use_container_width=True):
            target = infer_resume_page(dict(st.session_state))
            if not rgpd_is_current(st.session_state):
                st.session_state.rgpd_return_page = target
                st.session_state.navigation_page = "rgpd"
            else:
                st.session_state.navigation_page = target
            st.rerun()
        return

    if not rgpd_is_current(st.session_state):
        st.markdown("## Avant de commencer")
        st.info("Prenez d’abord connaissance des informations RGPD. Cette validation ne vous sera demandée qu’une fois pour cette version du texte.")
        if st.button("Lire les informations RGPD", type="primary", use_container_width=True):
            st.session_state.rgpd_return_page = "accueil"
            st.session_state.navigation_page = "rgpd"
            st.rerun()
        return

    st.markdown("## Accès public — découvrez gratuitement votre profil")
    st.caption("Identifiez-vous puis confirmez votre adresse e-mail avec le code reçu. Vos coordonnées ne sont pas intégrées à un dossier bénéficiaire Clarté360.")
    identity = st.session_state.get("public_identity", {})
    c1,c2=st.columns(2)
    with c1:
        first=st.text_input("Prénom *", value=identity.get("first_name",""), max_chars=100)
        job=st.text_input("Fonction / titre (facultatif)", value=identity.get("job_title",""), max_chars=200)
        phone=st.text_input("Téléphone *", value=identity.get("phone",""), max_chars=40)
    with c2:
        last=st.text_input("Nom *", value=identity.get("last_name",""), max_chars=100)
        company=st.text_input("Entreprise / organisation (facultatif)", value=identity.get("company",""), max_chars=200)
        email=st.text_input("E-mail *", value=identity.get("email",""), max_chars=254)
    st.markdown("### Mes centres d’intérêt (facultatif)")
    interest_options = [
        "Bilan de compétences",
        "Coaching professionnel — atteindre un objectif",
        "Formation individuelle — programme sur mesure",
        "Solutions collectives pour mon entreprise",
        "Autre",
    ]
    interests=st.multiselect("Ce qui peut m’intéresser chez Clarté360", interest_options, default=st.session_state.get("public_interests", []))
    other_interest = st.text_input("Autre intérêt (facultatif)", value=st.session_state.get("public_other_interest", ""), max_chars=500) if "Autre" in interests else ""
    marketing=st.checkbox("Je souhaite recevoir les actualités, ressources et offres Clarté360. (facultatif et indépendant de mes centres d’intérêt)", value=bool(st.session_state.get("public_marketing_opt_in",False)))
    current={"first_name":first,"last_name":last,"job_title":job,"company":company,"phone":phone,"email":email}
    if not st.session_state.get("public_access_verified"):
        if st.button("Recevoir mon code d’accès", type="primary", use_container_width=True):
            errors=validate_public_identity(current)
            if errors:
                for e in errors: st.error(e)
            else:
                participant_id=st.session_state.get("public_participant_id") or str(uuid4())
                current = validated_public_identity(current)
                st.session_state.public_participant_id=participant_id; st.session_state.public_identity=current; st.session_state.public_marketing_opt_in=bool(marketing); st.session_state.public_interests=list(interests); st.session_state.public_other_interest=other_interest
                save_public_lead(participant_id,current,marketing,False,interests,other_interest)
                ok,msg,state=issue_public_code(current,load_smtp_settings(st.secrets))
                if ok:
                    st.session_state.public_code_state=state; st.success("Code envoyé. Consultez votre messagerie puis saisissez-le ci-dessous.")
                else: st.error(msg)
        if st.session_state.get("public_code_state"):
            code=st.text_input("Code d’accès reçu par e-mail", max_chars=6)
            if st.button("Valider mon code", use_container_width=True):
                if verify_public_code(code,st.session_state.public_code_state):
                    st.session_state.public_access_verified=True
                    st.session_state.public_email_verified_at = st.session_state.get("public_email_verified_at") or _utcnow()
                    save_public_lead(st.session_state.public_participant_id,st.session_state.public_identity,st.session_state.public_marketing_opt_in,True,st.session_state.get("public_interests",[]),st.session_state.get("public_other_interest",""))
                    _publish_public_contact_event("CONTACT_EMAIL_VERIFIED", {"email_verified_at": st.session_state.public_email_verified_at})
                    st.success("Adresse e-mail vérifiée. Votre accès est ouvert."); st.rerun()
                else: st.error("Code incorrect, expiré ou nombre maximal d’essais atteint.")
    else:
        st.success(f"Accès vérifié pour {st.session_state.public_identity.get('first_name','')} {st.session_state.public_identity.get('last_name','')}.")
        label = "Reprendre mon profil RIASEC" if st.session_state.get("pip_state", {}).get("order") else "Commencer mon profil RIASEC"
        if st.button(label, type="primary", use_container_width=True):
            st.session_state.navigation_page = infer_resume_page(dict(st.session_state))
            st.rerun()


def render_pip_intro() -> None:
    st.subheader("Avant la passation PIP")
    st.success("Consentement enregistré.")
    st.markdown("Le PIP explore votre **attraction / intérêt**. Il ne mesure ni compétence, ni aptitude, ni intelligence, ni personnalité.")
    bank = load_pip_bank(); assert_valid_bank(bank)
    st.info("72 activités professionnelles · réponses de 1 à 5 · aucun score pendant la passation.")
    st.markdown(f"**Consigne :** {bank['response_instruction']}")
    st.markdown("### Et O*NET ?")
    st.markdown("**O*NET Interest Profiler** est l’outil américain officiel d’exploration des intérêts professionnels. La version proposée comporte **60 activités en anglais**, avec une échelle de 1 (Strongly Dislike) à 5 (Strongly Like). Il est distinct du PIP Clarté360 et permet une seconde mesure RIASEC utile pour une comparaison descriptive.")
    st.caption("Si vous choisissez O*NET maintenant, vos résultats PIP resteront masqués jusqu’à la fin des 60 questions O*NET afin d’éviter d’influencer vos réponses. Vous pourrez aussi décider de faire O*NET plus tard après votre résultat PIP ; cette chronologie sera alors enregistrée dans les données d’étude.")
    choices = ["PIP_SEUL", "PIP_PUIS_ONET60"]
    existing_journey = st.session_state.get("journey", "PIP_SEUL")
    journey = st.radio(
        "Mon parcours",
        choices,
        index=choices.index(existing_journey) if existing_journey in choices else 0,
        format_func=lambda x: "PIP seul — je verrai mon résultat après les 72 questions" if x == "PIP_SEUL" else "PIP puis O*NET 60 en anglais — résultats PIP masqués jusqu’à la fin d’O*NET",
    )
    existing_pip = st.session_state.get("pip_state", {}) or {}
    has_progress = bool(existing_pip.get("order") or existing_pip.get("answers"))
    if not has_progress:
        st.session_state.journey = journey
        st.session_state.onet_selected_timing = "PRE_PIP" if journey == "PIP_PUIS_ONET60" else None
    else:
        st.info("Une passation PIP existe déjà. Elle sera reprise sans effacer vos réponses ni votre choix de parcours.")
    button_label = "Reprendre le PIP" if has_progress else "Démarrer le PIP"
    if st.button(button_label, type="primary", use_container_width=True):
        if not has_progress:
            bank = load_pip_bank(); assert_valid_bank(bank)
            st.session_state.pip_state = {"bank_version": bank["bank_version"], "order": build_order(bank, st.session_state.passation_id), "answers": {}, "index": 0}
        st.session_state.navigation_page = infer_resume_page(dict(st.session_state))
        _save_if_accompanied(); _publish_if_accompanied("EN_COURS")
        st.rerun()


def render_pip_questionnaire() -> None:
    ps = st.session_state.pip_state
    bank = load_pip_bank(bank_version=ps.get("bank_version") if isinstance(ps, dict) else None); assert_valid_bank(bank)
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
                if st.session_state.get("journey", "PIP_SEUL") != "PIP_SEUL":
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
        downloaded = st.download_button(
            "💾 Sauvegarder et quitter plus tard (JSON)",
            data=snapshot_bytes(dict(st.session_state)),
            file_name="pip_clarte360_sauvegarde.json",
            mime="application/json",
            use_container_width=True,
        )
        if downloaded:
            mark_public_work_saved(st.session_state)
        st.caption("Votre sauvegarde permet de reprendre au même endroit. Aucun résultat intermédiaire n’est exporté.")
    else:
        _save_if_accompanied()
        st.info("Sauvegarde automatique Clarté360 active. Vous pourrez reprendre depuis votre espace bénéficiaire.")




def _render_pip_report_preview_before_feeling() -> None:
    """Show substantive PIP report pages before asking the participant to rate the profile."""
    try:
        pdf_bytes = build_pip_report_pdf(dict(st.session_state), ASSETS_DIR / "logo_clarte360.png")
        preview_pages = pdf_pages_as_png(pdf_bytes, 3, 4)
    except Exception as exc:
        st.warning(f"La prévisualisation du rapport n’a pas pu être générée : {exc}")
        return
    st.markdown("### Prenez connaissance de votre synthèse avant de donner votre ressenti")
    st.markdown(
        "Consultez ci-dessous les pages essentielles de votre rapport PIP : le **profil global**, "
        "l’**interprétation de vos dimensions dominantes** et les **facettes qui nuancent votre profil**. "
        "Elles sont affichées directement dans Clarté360 afin d’éviter les blocages des lecteurs PDF intégrés aux navigateurs."
    )
    for page_number, image_bytes in enumerate(preview_pages, start=3):
        st.caption(f"Rapport PIP — page {page_number}")
        st.image(image_bytes, use_container_width=True)
    st.download_button(
        "Ouvrir / télécharger la synthèse PIP complète en PDF",
        data=pdf_bytes,
        file_name="rapport_pip_riasec_clarte360.pdf",
        mime="application/pdf",
        use_container_width=True,
        key="download_pip_preview_before_feeling",
    )
    st.info("Après avoir pris connaissance de cette synthèse, vous pourrez donner votre ressenti sur le profil présenté.")


def render_pip_results() -> None:
    scoring = st.session_state.get("pip_scoring", {})
    if not scoring or not scoring.get("complete"):
        st.error("La restitution nécessite une passation PIP complète.")
        return
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
    st.markdown("---")
    if st.session_state.get("journey", "PIP_SEUL") == "PIP_SEUL" and not st.session_state.get("onet_state", {}).get("completed"):
        st.markdown("### Vous voulez aller plus loin ?")
        st.markdown("Vous pouvez maintenant passer l’**O*NET Interest Profiler 60**, en anglais. C’est un questionnaire officiel américain distinct du PIP. Comme vous avez déjà vu votre résultat PIP, cette passation sera identifiée comme **O*NET choisi après restitution PIP** dans les données d’étude.")
        if st.button("Passer aussi O*NET 60", use_container_width=True):
            st.session_state.journey="PIP_PUIS_ONET60"
            st.session_state.onet_selected_timing="POST_PIP_RESULTS"
            st.session_state.navigation_page="onet_intro"; st.rerun()
    st.markdown("---")
    _render_pip_report_preview_before_feeling()
    if st.button("J’ai consulté ma synthèse — donner mon ressenti", type="primary", use_container_width=True):
        st.session_state.navigation_page = "feeling"; st.rerun()


def render_feeling() -> None:
    st.subheader("Votre ressenti sur le profil")
    st.caption("Vous avez maintenant consulté une restitution détaillée de votre profil. Ce questionnaire fermé compare votre ressenti à cette restitution sans modifier le scoring PIP.")
    answers = {}
    scale = [1, 2, 3, 4, 5]
    labels = {1:"Pas du tout",2:"Plutôt non",3:"Partagé(e)",4:"Plutôt oui",5:"Tout à fait"}
    for key in ("global", "dominants", "nuances", "useful"):
        q = QUESTIONS[key]
        answers[key] = st.radio(q["text"], scale, index=None, format_func=lambda x: f"{x} — {labels[x]}", key=f"feel_{key}")
    answers["over"] = st.selectbox(QUESTIONS["over"]["text"], ["Aucune", "R", "I", "A", "S", "E", "C"], key="feel_over")
    answers["under"] = st.selectbox(QUESTIONS["under"]["text"], ["Aucune", "R", "I", "A", "S", "E", "C"], key="feel_under")
    launch = st.session_state.get("launch_context")
    callback_choice = None
    if launch and launch.mode is RunMode.PUBLIC:
        st.markdown("### Être recontacté(e) par Clarté360")
        callback_choice = st.radio(
            "Souhaitez-vous être recontacté(e) par Clarté360 pour échanger sur vos résultats ou votre projet ?",
            ["NON", "OUI"],
            index=None,
            format_func=lambda x: "Non" if x == "NON" else "Oui",
            key="public_callback_choice",
        )
        st.caption("Si vous choisissez Oui, votre demande transmet uniquement vos coordonnées et votre souhait d’être rappelé(e). Vos scores, votre profil RIASEC et vos réponses ne sont pas transmis avec cette demande.")
    required = [answers[k] for k in ("global", "dominants", "nuances", "useful")]
    callback_missing = bool(launch and launch.mode is RunMode.PUBLIC and callback_choice is None)
    if st.button("Valider mon ressenti", type="primary", disabled=any(v is None for v in required) or callback_missing, use_container_width=True):
        launch = st.session_state.get("launch_context")
        run_mode = launch.mode.value if launch else None
        st.session_state.feeling = build_feeling_record(
            answers,
            st.session_state.get("journey", "PIP_SEUL"),
            "PIP-RPT-L1-MIN",
            run_mode=run_mode,
        )
        launch=st.session_state.get("launch_context")
        if launch and launch.mode is RunMode.PUBLIC:
            st.session_state.public_callback_requested = callback_choice == "OUI"
            if callback_choice == "OUI":
                requested_at = st.session_state.get("public_callback_requested_at") or _utcnow()
                st.session_state.public_callback_requested_at = requested_at
                # Deliberately contains no scores, RIASEC profile or raw answers.
                payload = _public_contact_payload()
                callback_payload = {
                    "source": "PIP_PUBLIC",
                    "first_name": payload.get("first_name"),
                    "last_name": payload.get("last_name"),
                    "email": payload.get("email"),
                    "phone": payload.get("phone"),
                    "requested_at": requested_at,
                    "reason": "ECHANGER_RESULTATS_OU_PROJET",
                }
                GestionActionsPort(None).publish_event("CALLBACK_REQUESTED", callback_payload)
            if st.session_state.get("study_consent"):
                save_public_study_record(st.session_state)
        st.session_state.navigation_page = "finished"; st.rerun()


def render_finished() -> None:
    st.success("Votre parcours PIP est terminé.")
    launch = st.session_state.get("launch_context")
    try:
        pdf_bytes = build_pip_report_pdf(dict(st.session_state), ASSETS_DIR / "logo_clarte360.png")
        st.session_state.report_version = PIP_REPORT_VERSION
        st.download_button("Télécharger mon rapport PIP RIASEC Clarté360", data=pdf_bytes, file_name="rapport_pip_riasec_clarte360.pdf", mime="application/pdf", type="primary", use_container_width=True)
        onet_pdf = None
        if st.session_state.get("onet_state", {}).get("completed"):
            onet_pdf = build_onet_report_pdf(dict(st.session_state), ASSETS_DIR / "logo_clarte360.png")
            st.session_state.onet_report_version = ONET_REPORT_VERSION
            st.download_button("Télécharger mon rapport O*NET Interest Profiler", data=onet_pdf, file_name="rapport_onet_interest_profiler.pdf", mime="application/pdf", use_container_width=True)

        if launch and launch.mode is RunMode.ACCOMPANIMENT:
            # TERMINE is emitted only here: after feeling and successful PDF generation.
            if not st.session_state.get("completed_at"):
                st.session_state.completed_at = _utcnow()
            refs = list(st.session_state.get("report_documents") or [])
            if not refs:
                refs.append(persist_report_document(st.session_state.passation_id, "rapport_pip_riasec_clarte360.pdf", pdf_bytes))
                if onet_pdf is not None:
                    refs.append(persist_report_document(st.session_state.passation_id, "rapport_onet_interest_profiler.pdf", onet_pdf))
                st.session_state.report_documents = refs
            if not st.session_state.get("final_event_published"):
                GestionActionsPort(None).publish_event("TERMINE", _accompanied_final_payload(refs))
                st.session_state.final_event_published = True
            _save_if_accompanied()
            st.markdown("Votre profil, votre ressenti et le ou les rapports sont disponibles dans votre parcours Clarté360.")
        elif launch and launch.mode is RunMode.PUBLIC:
            if st.session_state.get("public_callback_requested"):
                st.success("Votre demande de rappel a bien été enregistrée. Vos résultats PIP/O*NET n’ont pas été transmis avec cette demande.")
            st.caption("Vous pouvez aussi conserver la sauvegarde technique JSON pour reprendre ou archiver cette session.")
            downloaded = st.download_button("Télécharger ma sauvegarde finale (JSON)", data=snapshot_bytes(dict(st.session_state)), file_name="pip_clarte360_final.json", mime="application/json", use_container_width=True)
            if downloaded:
                mark_public_work_saved(st.session_state)
    except Exception as exc:
        st.error(f"Le rapport PDF n’a pas pu être généré : {exc}")


def _onet_port() -> OnetPort:
    return OnetPort(load_onet_settings(st.secrets))

def render_onet_pending() -> None:
    st.session_state.navigation_page="onet_intro"
    st.rerun()

def render_onet_intro() -> None:
    st.success("Votre PIP est terminé.")
    pre = st.session_state.get("onet_selected_timing") == "PRE_PIP"
    if pre:
        st.warning("Vous aviez choisi PIP + O*NET avant de commencer : votre résultat PIP reste volontairement masqué jusqu’à la fin d’O*NET.")
    st.subheader("O*NET Interest Profiler — 60 questions en anglais")
    st.markdown("O*NET® Interest Profiler est développé aux États-Unis et explore lui aussi les intérêts selon les six dimensions RIASEC. **Ce n’est pas une traduction du PIP Clarté360**. Clarté360 vous présente les 60 activités en anglais, telles qu’elles sont fournies par O*NET Web Services, sans les traduire ni les reformuler. Ce choix permet de conserver l’instrument dans son format de référence. Votre rapport pourra ensuite être expliqué en français, en distinguant clairement les résultats officiels O*NET des commentaires pédagogiques Clarté360.")
    st.info("Échelle officielle : 1 — Strongly Dislike · 2 — Dislike · 3 — Unsure · 4 — Like · 5 — Strongly Like")
    st.caption("Source : O*NET Interest Profiler / O*NET Web Services. Les résultats O*NET sont conservés séparément des résultats PIP et leur comparaison reste descriptive.")
    port=_onet_port()
    if not port.configured:
        st.error("Le service O*NET n’est pas configuré sur le serveur. La passation ne peut pas démarrer.")
        return
    if st.button("Démarrer O*NET 60", type="primary", use_container_width=True):
        try:
            data=port.fetch_interest_profiler()
            questions=data.get("question", [])
            if len(questions) != 60: raise OnetApiError(f"O*NET a retourné {len(questions)} questions au lieu de 60.")
            st.session_state.onet_state={"source":"O*NET Web Services API","api_version":ONET_API_VERSION,"instrument":ONET_INSTRUMENT,"language":ONET_LANGUAGE,"question_count":60,"questions":questions,"answer_options":data.get("answer_option", []),"answers":{},"index":0,"completed":False,"selected_timing":st.session_state.get("onet_selected_timing")}
            st.session_state.navigation_page="onet_questionnaire"; _save_if_accompanied(); st.rerun()
        except Exception as exc:
            st.error(str(exc))

def render_onet_questionnaire() -> None:
    state=st.session_state.get("onet_state", {})
    questions=state.get("questions", [])
    if len(questions) != 60:
        st.error("La série O*NET 60 n’est pas chargée correctement."); return
    idx=int(state.get("index",0)); q=questions[idx]; qidx=int(q.get("index",idx+1))
    st.progress((idx+1)/60, text=f"O*NET — Question {idx+1} sur 60")
    st.caption("Official O*NET Interest Profiler — English version")
    st.subheader(str(q.get("text", "")))
    labels={1:"Strongly Dislike",2:"Dislike",3:"Unsure",4:"Like",5:"Strongly Like"}
    current=state.get("answers",{}).get(str(qidx))
    choice=st.radio("Your answer", [1,2,3,4,5], index=(int(current)-1 if current else None), format_func=lambda x:f"{x} — {labels[x]}", key=f"onet_{qidx}")
    if choice is not None:
        state.setdefault("answers", {})[str(qidx)] = choice
    c1,c2=st.columns(2)
    with c1:
        if st.button("Previous", disabled=idx==0, use_container_width=True):
            if choice is not None: state.setdefault("answers",{})[str(qidx)]=choice
            state["index"]=idx-1; _save_if_accompanied(); st.rerun()
    with c2:
        if st.button("Finish O*NET" if idx==59 else "Next", type="primary", disabled=choice is None, use_container_width=True):
            state.setdefault("answers",{})[str(qidx)]=choice
            if idx==59:
                try:
                    result=_onet_port().score_interest_profiler(state["answers"])
                    state["results_api_order"]=result.get("result", [])
                    state["results"]=normalize_onet_results(result.get("result", []))
                    state["completed"]=True
                    state["index"]=59
                    st.session_state.navigation_page="combined_results"
                    _save_if_accompanied()
                except Exception as exc:
                    st.error(str(exc)); return
            else:
                state["index"]=idx+1; _save_if_accompanied()
            st.rerun()

    launch = st.session_state.get("launch_context")
    if launch and launch.mode is RunMode.PUBLIC:
        st.markdown("---")
        downloaded = st.download_button(
            "💾 Sauvegarder et quitter plus tard (JSON)",
            data=snapshot_bytes(dict(st.session_state)),
            file_name="pip_clarte360_sauvegarde.json",
            mime="application/json",
            use_container_width=True,
            key="download_onet_pause_json",
        )
        if downloaded:
            mark_public_work_saved(st.session_state)

def render_combined_results() -> None:
    if not st.session_state.get("onet_state",{}).get("completed"):
        st.error("La restitution O*NET nécessite les 60 réponses."); return
    st.success("PIP et O*NET terminés")
    st.subheader("Votre profil PIP RIASEC Clarté360")
    scoring=st.session_state.get("pip_scoring",{})
    for d in scoring.get("order",[]):
        st.markdown(f"**{d} — {DIMENSION_LABELS[d]}** : {float(scoring['indices'][d]):.0f} / 100")
    st.subheader("Votre profil O*NET Interest Profiler")
    code_map={"realistic":"R","investigative":"I","artistic":"A","social":"S","enterprising":"E","conventional":"C"}
    st.caption("Classement O*NET présenté par score officiel décroissant. Les scores O*NET restent sur leur échelle propre et ne sont pas convertis sur l’indice PIP 0–100.")
    for r in normalize_onet_results(st.session_state.onet_state.get("results",[])):
        code=code_map.get(str(r.get("code","")).lower(), str(r.get("code","")))
        st.markdown(f"**{code} — {r.get('title','')}** : {r.get('score','—')}")
    st.info("Les deux outils sont distincts. Le PIP et O*NET s’appuient tous deux sur les six intérêts RIASEC, mais leurs questions et leurs échelles de score sont propres à chaque instrument. La comparaison porte sur les rangs et les dominantes ; les valeurs numériques ne sont ni fusionnées ni moyennées et ne produisent pas automatiquement une orientation ou un classement de métiers.")
    if st.session_state.get("onet_selected_timing") == "POST_PIP_RESULTS":
        st.caption("O*NET a été choisi après consultation du résultat PIP ; cette chronologie est conservée pour l’analyse méthodologique.")
    launch=st.session_state.get("launch_context")
    if launch and launch.mode is RunMode.PUBLIC and st.session_state.get("study_consent"):
        save_public_study_record(dict(st.session_state))
    st.markdown("---")
    _render_pip_report_preview_before_feeling()
    if st.button("J’ai consulté ma synthèse — donner mon ressenti", type="primary", use_container_width=True):
        st.session_state.navigation_page="feeling"; st.rerun()


def render_results_gate() -> None:
    allowed = results_allowed(st.session_state.get("journey", "PIP_SEUL"), bool(st.session_state.get("pip_state", {}).get("completed")), bool(st.session_state.get("onet_state", {}).get("completed")))
    if not allowed:
        st.error("Résultats verrouillés jusqu’à la fin du parcours prévu.")
        return
    render_pip_results()


def render_timeout() -> None:
    st.warning("Votre session a été interrompue pour inactivité. Votre travail n’est pas perdu. Ne fermez pas cette fenêtre avant d’avoir téléchargé votre sauvegarde de reprise.")
    downloaded = st.download_button(
        "TÉLÉCHARGER MA SAUVEGARDE AVANT DE QUITTER",
        data=snapshot_bytes(dict(st.session_state)),
        file_name="pip_clarte360_reprise_timeout.json",
        mime="application/json",
        type="primary",
        use_container_width=True,
    )
    if downloaded:
        mark_public_work_saved(st.session_state)
        st.success("Sauvegarde téléchargée. Un seul téléchargement suffit.")
    else:
        st.caption("Un seul téléchargement suffit. Ce fichier permet de reprendre directement à la dernière étape utile.")

    st.markdown("### Reprendre maintenant avec une sauvegarde")
    uploaded = st.file_uploader("Sélectionnez votre sauvegarde JSON", type=["json"], key="timeout_resume_json")
    if uploaded is not None and st.button("Reprendre", type="primary", use_container_width=True, key="timeout_resume_button"):
        try:
            payload = decode_snapshot_bytes(uploaded.getvalue())
            restore_snapshot(payload, st.session_state)
            mark_public_work_saved(st.session_state)
            st.success("Sauvegarde restaurée.")
            st.rerun()
        except Exception as exc:
            st.error(f"Sauvegarde incompatible : {exc}")


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
    elif page == "onet_intro": render_onet_intro()
    elif page == "onet_questionnaire": render_onet_questionnaire()
    elif page == "combined_results": render_combined_results()
    elif page == "contact": render_contact()
    elif page == "timeout": render_timeout()
    else: st.error("Écran indisponible.")
