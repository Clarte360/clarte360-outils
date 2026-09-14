from __future__ import annotations

import json
from uuid import uuid4
import streamlit as st

from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.framework.config import LOGO_PATH, ASSETS_DIR, load_smtp_settings, load_onet_settings
from clarte360_pip.framework.contact import render_contact
from clarte360_pip.framework.persistence import snapshot_bytes, restore_snapshot
from clarte360_pip.framework.unsaved_guard import mark_public_work_saved
from clarte360_pip.scoring import score_pip
from clarte360_pip.journey import results_allowed, next_after_pip
from clarte360_pip.framework.rgpd import render_rgpd
from clarte360_pip.pip_data.loader import load_pip_bank
from clarte360_pip.pip_data.validation import assert_valid_bank
from clarte360_pip.questionnaire import QuestionnaireEngine, build_order
from clarte360_pip.feeling import QUESTIONS, build_feeling_record
from clarte360_pip.framework.server_store import save_accompanied_snapshot
from clarte360_pip.connectors.gestion_actions import GestionActionsPort
from clarte360_pip.connectors.onet import OnetPort, OnetApiError
from clarte360_pip.framework.public_access import (validate_public_identity, validated_public_identity, issue_public_code, verify_public_code, save_public_lead, save_public_study_record)



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
    st.markdown("# Découvrez ce qui vous attire vraiment dans le travail")
    st.markdown("### Votre Profil d’Intérêts Professionnels RIASEC Clarté360")
    st.markdown("""
<div class="clarte-hero">
<b>Le RIASEC, c’est une boussole pour mieux comprendre vos préférences professionnelles.</b><br><br>
Le modèle de Holland distingue six grandes familles d’intérêts : <b>Réaliste, Investigateur, Artistique, Social, Entreprenant et Conventionnel</b>.
Le PIP Clarté360 explore, au travers de 120 situations concrètes, les activités, situations et environnements qui vous attirent le plus — et ceux qui vous attirent moins.
</div>
""", unsafe_allow_html=True)
    st.markdown("**À l’issue du questionnaire :** découvrez vos six dimensions RIASEC et, lorsque les résultats le permettent, votre code de synthèse Holland. Ce profil n’est ni un test de compétences ni un verdict : il éclaire vos préférences et vos choix professionnels.")
    st.markdown('<div class="clarte-stats"><b>120 situations</b> &nbsp; • &nbsp; <b>≈ 15–20 min</b> &nbsp; • &nbsp; <b>Résultat personnel</b> &nbsp; • &nbsp; <b>Sauvegarde possible</b></div>', unsafe_allow_html=True)

    if launch.mode is RunMode.ACCOMPANIMENT:
        st.success("Accès bénéficiaire Clarté360 reconnu.")
        if st.session_state.get("server_resume_restored"): st.info("Votre passation précédente a été retrouvée automatiquement.")
        st.markdown(f"**Action :** {launch.action_id}  \n**Bénéficiaire :** {launch.beneficiary_id}")
        st.caption("Cet outil vous a été adressé depuis votre parcours Clarté360. Votre progression est sauvegardée automatiquement.")
        if not st.session_state.get("consulted_event_published"):
            _publish_if_accompanied("CONSULTE"); st.session_state.consulted_event_published=True
        if st.button("Commencer / reprendre mon PIP", type="primary", use_container_width=True):
            st.session_state.navigation_page="rgpd"; st.rerun()
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
                    save_public_lead(st.session_state.public_participant_id,st.session_state.public_identity,st.session_state.public_marketing_opt_in,True,st.session_state.get("public_interests",[]),st.session_state.get("public_other_interest",""))
                    st.success("Adresse e-mail vérifiée. Votre accès est ouvert."); st.rerun()
                else: st.error("Code incorrect, expiré ou nombre maximal d’essais atteint.")
    else:
        st.success(f"Accès vérifié pour {st.session_state.public_identity.get('first_name','')} {st.session_state.public_identity.get('last_name','')}.")
        if st.button("Commencer mon profil RIASEC", type="primary", use_container_width=True):
            st.session_state.navigation_page="rgpd"; st.rerun()


def render_pip_intro() -> None:
    st.subheader("Avant la passation PIP")
    st.success("Consentement enregistré.")
    st.markdown("Le PIP explore votre **attraction / intérêt**. Il ne mesure ni compétence, ni aptitude, ni intelligence, ni personnalité.")
    st.info("120 propositions pilotes · réponses de 1 à 5 · exemples concrets pour limiter les interprétations ambiguës · aucun score pendant la passation.")
    st.markdown("### Et O*NET ?")
    st.markdown("**O*NET Interest Profiler** est l’outil américain officiel d’exploration des intérêts professionnels. La version proposée comporte **60 activités en anglais**, avec une échelle de 1 (Strongly Dislike) à 5 (Strongly Like). Il est distinct du PIP Clarté360 et permet une seconde mesure RIASEC utile pour une comparaison descriptive.")
    st.caption("Si vous choisissez O*NET maintenant, vos résultats PIP resteront masqués jusqu’à la fin des 60 questions O*NET afin d’éviter d’influencer vos réponses. Vous pourrez aussi décider de faire O*NET plus tard après votre résultat PIP ; cette chronologie sera alors enregistrée dans les données d’étude.")
    journey = st.radio(
        "Mon parcours",
        ["PIP_SEUL", "PIP_PUIS_ONET60"],
        format_func=lambda x: "PIP seul — je verrai mon résultat après les 120 questions" if x == "PIP_SEUL" else "PIP puis O*NET 60 en anglais — résultats PIP masqués jusqu’à la fin d’O*NET",
    )
    st.session_state.journey = journey
    st.session_state.onet_selected_timing = "PRE_PIP" if journey == "PIP_PUIS_ONET60" else None
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
    if st.button("Continuer vers mon ressenti", type="primary", use_container_width=True):
        st.session_state.navigation_page = "feeling"; st.rerun()


def render_feeling() -> None:
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
        launch=st.session_state.get("launch_context")
        if launch and launch.mode is RunMode.PUBLIC and st.session_state.get("study_consent"):
            save_public_study_record(dict(st.session_state))
        st.session_state.navigation_page = "finished"; st.rerun()


def render_finished() -> None:
    st.success("Votre parcours PIP est terminé.")
    launch = st.session_state.get("launch_context")
    if launch and launch.mode is RunMode.PUBLIC:
        st.markdown("Votre profil et votre ressenti ont été enregistrés dans la session en cours.")
        downloaded = st.download_button("Télécharger ma sauvegarde finale (JSON)", data=snapshot_bytes(dict(st.session_state)), file_name="pip_clarte360_final.json", mime="application/json", use_container_width=True)
        if downloaded:
            mark_public_work_saved(st.session_state)
    else:
        _save_if_accompanied()
        st.markdown("Votre profil et votre ressenti ont été enregistrés dans votre parcours Clarté360.")


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
    st.markdown("O*NET est développé aux États-Unis et mesure lui aussi les intérêts selon les six dimensions RIASEC. **Ce n’est pas une traduction du PIP Clarté360** : vous allez répondre aux 60 activités officielles en anglais, sans traduction automatique des questions.")
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
            st.session_state.onet_state={"source":"O*NET Web Services API v2","language":"en","questions":questions,"answer_options":data.get("answer_option", []),"answers":{},"index":0,"completed":False}
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
                    state["results"]=result.get("result", [])
                    state["completed"]=True
                    state["index"]=59
                    st.session_state.navigation_page="combined_results"
                    _save_if_accompanied(); _publish_if_accompanied("TERMINE")
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
    for r in st.session_state.onet_state.get("results",[]):
        code=code_map.get(str(r.get("code","")).lower(), str(r.get("code","")))
        st.markdown(f"**{code} — {r.get('title','')}** : {r.get('score','—')}")
    st.info("Les deux outils sont distincts. Cette présentation côte à côte est descriptive : elle ne fusionne pas les scores et ne produit pas automatiquement une orientation ou un classement de métiers.")
    if st.session_state.get("onet_selected_timing") == "POST_PIP_RESULTS":
        st.caption("O*NET a été choisi après consultation du résultat PIP ; cette chronologie est conservée pour l’analyse méthodologique.")
    launch=st.session_state.get("launch_context")
    if launch and launch.mode is RunMode.PUBLIC and st.session_state.get("study_consent"):
        save_public_study_record(dict(st.session_state))
    if st.button("Continuer vers mon ressenti", type="primary", use_container_width=True):
        st.session_state.navigation_page="feeling"; st.rerun()


def render_results_gate() -> None:
    allowed = results_allowed(st.session_state.get("journey", "PIP_SEUL"), bool(st.session_state.get("pip_state", {}).get("completed")), bool(st.session_state.get("onet_state", {}).get("completed")))
    if not allowed:
        st.error("Résultats verrouillés jusqu’à la fin du parcours prévu.")
        return
    render_pip_results()


def render_timeout() -> None:
    st.warning("Session interrompue pour inactivité.")
    downloaded = st.download_button("Télécharger la sauvegarde de reprise", data=snapshot_bytes(dict(st.session_state)), file_name="pip_clarte360_reprise_timeout.json", mime="application/json", type="primary")
    if downloaded:
        mark_public_work_saved(st.session_state)


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
