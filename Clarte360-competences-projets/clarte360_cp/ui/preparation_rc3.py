"""GO22 RC3 - deux vues Streamlit, accompagnateur et bénéficiaire.

C-AV1 (0/1/n piste) puis C-AV2 (3 familles de choix). Q validée AVANT
l'ouverture d'accès; R1 soumise une seule fois APRES deux étapes enregistrées.
C-AV3 est réservé à l'accompagnateur et utilise le contrat IA partagé ;
aucun appel IA n'est effectué pendant la passation bénéficiaire.
"""
from __future__ import annotations

import copy

from clarte360_cp.application.preparation import (
    create_questionnaire_v2, save_questionnaire, lock_questionnaire, lock_and_publish_questionnaire,
    open_beneficiary_access, read_preparation, save_beneficiary_answers,
    submit_beneficiary_answers, save_joint_review, confirm_joint_review,
    response_history, cav3_context,
)
from clarte360_cp.domain.preparation import (
    CAV1_MEANINGS,CAV1_STATUSES,CAV1_ATTRACTIONS,CAV1_ACCESS,
    CONTEXTS, ENTERPRISE_RESPONSES,
)
from clarte360_cp.domain.preparation_v2 import (
    SCHEMA_Q_V2, REASON_NONE, INTEREST_CHOICES, CHOICE_POLE,
    CHOICE_IMPORTANCE, SITUATION_CHOICES, MOTOR_LABELS,
    new_idea, adapt_context_question, empty_answers_v2, DEFAULT_CONTEXT_CHOICES,
)
from clarte360_cp.domain.preparation import difference

CONTEXT_LABELS={"AUTOFINANCE":"Autofinancement", "ENTREPRISE_TRIPARTITE":"Convention tripartite autorisée",
 "ENTREPRISE_TRIPARTITE_MIXTE":"Tripartite et cofinancement", "FINANCEMENT_MIXTE":"Financement mixte (sans droit employeur automatique)", "AUTRE":"Autre"}
STATUS_LABELS={"EXPLORER":"Je souhaite encore explorer cette piste",
 "ACTIVITES_LIEES":"Je souhaite surtout explorer certaines activités associées",
 "NON_ACTUELLEMENT":"Cette piste ne m'intéresse plus pour le moment",
 "INDECISE":"Je ne sais pas encore"}
POLE_LABELS={"POLE_1":"Plutôt le premier pôle", "EQUILIBRE":"Un équilibre entre les deux", "POLE_2":"Plutôt le deuxième pôle", "AUTRE":"Une autre façon, à préciser"}
IMPORTANCE_LABELS={"INDISPENSABLE":"Indispensable", "IMPORTANT_ADAPTABLE":"Important, mais je peux m'adapter"}
NONE_OPTIONS=("",*REASON_NONE)
NONE_LABELS={"":"Choisissez si aucune priorité n'est retenue", "AUCUN_CRITERE_IDENTIFIE":"Aucune priorité déterminante aujourd'hui", "A_AFFINER":"J'ai réfléchi mais je ne peux pas encore hiérarchiser"}
SIT_LABELS={"OUI":"Oui, une situation précise", "NON":"Non", "PAS_IDENTIFIEE":"Je n'en ai pas identifié"}
ENTERPRISE_LABELS={"NE_SOUHAITE_PAS":"Je ne souhaite pas explorer cette perspective", "SOUHAITE_EXPLORER":"Je souhaite l'explorer", "SOUHAITE_CLARIFIER":"Je souhaite en clarifier le sens", "NE_SAIS_PAS":"Je ne sais pas encore"}


def _err(exc):
    import streamlit as st
    st.error(str(exc))


def _current_document_gate(ctx, case_id):
    """Refresh GDA inventory and return the D5 decisions required before Q."""
    import streamlit as st
    from clarte360_cp.connectors.gda_documents import GDAError, GDADocumentClient, load_gda_settings
    from clarte360_cp.repositories.db import build_engine, session_factory
    from clarte360_cp.repositories.gda_documents import (
        current_document_review_snapshot, list_current_gda_purpose_links,
        save_external_reference, unlinked_document_review_status,
    )

    settings = load_gda_settings(st.secrets)
    token = str(st.session_state.get("gda_launch_token", ""))
    if not settings.configured and not token:
        return {"connected": False, "pending": [], "verified_sources": {}, "error": None}
    if not settings.configured or not token or not ctx.has_scope("CP_SOURCE_GDA_READ"):
        return {"connected": True, "pending": [], "verified_sources": {},
                "error": "L’inventaire Gestion des Actions n’est pas accessible. Rouvrez Documents depuis l’action prescrite.", "has_inventory": True}
    try:
        external = GDADocumentClient(settings, token).list_sources()
        engine = build_engine()
        with session_factory(engine)() as session:
            live_docs = {str(item["source_ref"]): save_external_reference(session, ctx, case_id, item)
                         for item in external}
            links = list_current_gda_purpose_links(session, case_id)
            reviews = current_document_review_snapshot(session, case_id)
            verified = {}
            pending = []
            for purpose, row in reviews.items():
                doc = row["document"]
                live_doc = live_docs.get(doc.source_ref)
                if not live_doc:
                    pending.append(f"{doc.display_name} : pièce absente de l’inventaire partagé; vérifiez-la dans Documents")
                elif live_doc.external_document_id != doc.external_document_id:
                    if unlinked_document_review_status(session, case_id, live_doc) == "D5_DOCUMENT_NON_UTILISE":
                        continue
                    pending.append(f"{doc.display_name} : une nouvelle version est disponible; corrigez le rapprochement dans Documents")
                elif row["status"] == "A_VERIFIER":
                    pending.append(f"{doc.display_name} : vérification à faire pour {purpose}")
                elif row["status"] == "D5_DOCUMENT_VALIDE":
                    live = next((item for item in external if str(item["source_ref"]) == doc.source_ref), {})
                    if str(live.get("publication_status") or "").upper() == "PUBLIE":
                        verified[purpose] = row
            for ref, doc in live_docs.items():
                live = next((item for item in external if str(item["source_ref"]) == ref), {})
                active_purposes = [purpose for purpose, (linked_doc, _link) in links.items()
                                   if linked_doc.external_document_id == doc.external_document_id]
                stale_purposes = [purpose for purpose, (linked_doc, _link) in links.items()
                                  if linked_doc.source_ref == ref and linked_doc.external_document_id != doc.external_document_id
                                  and reviews.get(purpose, {}).get("status") not in {"D5_DOCUMENT_NON_UTILISE", "D5_DOCUMENT_VERIFIE_NON_UTILISE"}]
                current_excluded = unlinked_document_review_status(session, case_id, doc) == "D5_DOCUMENT_NON_UTILISE"
                if stale_purposes and not current_excluded:
                    pending.append(f"{doc.display_name} : remplacez la version reliée dans Documents")
                elif not active_purposes and not current_excluded:
                    pending.append(f"{doc.display_name} : à rapprocher ou à écarter dans Documents")
                elif active_purposes and str(live.get("publication_status") or "").upper() != "PUBLIE":
                    pending.append(f"{doc.display_name} : en attente de publication dans l’espace partagé")
            for purpose, (doc, _link) in links.items():
                if doc.source_ref not in live_docs:
                    pending.append(f"{doc.display_name} : pièce absente de l’inventaire partagé; vérifiez-la dans Documents")
            return {"connected": True, "pending": list(dict.fromkeys(pending)),
                    "verified_sources": verified, "error": None, "has_inventory": bool(external)}
    except GDAError as exc:
        return {"connected": True, "pending": [], "verified_sources": {}, "error": str(exc), "has_inventory": True}


def _create_questionnaire_from_documents(ctx, case_id, view, verified_sources, coach_observation=""):
    """Read the seven already-validated GDA references and save an AI-assisted draft."""
    import streamlit as st
    from clarte360_cp.connectors.cav3_ai import Cav3AISettings
    from clarte360_cp.connectors.gda_documents import GDADocumentClient, load_gda_settings
    from clarte360_cp.connectors.questionnaire_source_ai import analyze_questionnaire_sources
    from clarte360_cp.ui.preparation import SOURCE_LABELS
    from clarte360_cp.application.preparation import record_questionnaire_source_analysis_consent

    purpose_codes = tuple(item for item in (
        ("CV_SOURCE", "CV_SOURCE"), ("APS_OBJECTIF", "APS_OBJECTIF"),
        ("BOUSSOLE_VALEURS", "BOUSSOLE_VALEURS"), ("MOTEURS_PRO", "MOTEURS_PRO"),
        ("PREFERENCES_PRO", "PREFERENCES_PRO"), ("PIP_REPORT", "PIP_REPORT"),
        ("IPIP_REPORT", "IPIP_REPORT"),
    ) if item[0] in verified_sources)
    if not any(purpose == "APS_OBJECTIF" for purpose, _code in purpose_codes):
        raise ValueError("L’APS doit être retenue dans Documents pour générer les pistes du questionnaire.")
    settings = load_gda_settings(st.secrets)
    token = str(st.session_state.get("gda_launch_token", ""))
    gda = GDADocumentClient(settings, token)
    ai_sources, sources = [], {}
    for purpose, code in purpose_codes:
        doc = verified_sources[purpose]["document"]
        metadata, content = gda.get_source(str(doc.source_ref))
        label = "CV" if code == "CV_SOURCE" else SOURCE_LABELS[code]
        ai_sources.append({"purpose": purpose, "source_ref": doc.source_ref,
                           "label": label, "name": metadata.get("display_name") or doc.display_name,
                           "mime_type": metadata.get("mime_type") or doc.mime_type,
                           "content": content})
    record_questionnaire_source_analysis_consent(
        ctx, case_id, [source["source_ref"] for source in ai_sources])
    analysis = analyze_questionnaire_sources(ai_sources, Cav3AISettings.from_streamlit_secrets(),
                                             coach_observation=coach_observation)
    for purpose, code in purpose_codes:
        if purpose == "CV_SOURCE":
            doc = verified_sources[purpose]["document"]
            sources["CV_SOURCE"] = {"authorized": True, "source_ref": doc.source_ref, "label": "CV"}
            continue  # CV informs the APS context question; it is not a questionnaire report.
        doc = verified_sources[purpose]["document"]
        data = {"authorized": True, "source_ref": doc.source_ref, "label": SOURCE_LABELS[code]}
        if code in {"PIP_REPORT", "IPIP_REPORT"}:
            data["status"] = "REEL"
        if code == "APS_OBJECTIF":
            data["idea_details"] = analysis["ideas"]
        evidence_key = {"BOUSSOLE_VALEURS":"valeurs", "MOTEURS_PRO":"moteurs",
                        "PREFERENCES_PRO":"preferences", "PIP_REPORT":"pip",
                        "IPIP_REPORT":"ipip"}.get(code)
        if evidence_key:
            data["result_summary"] = analysis["evidence"].get(evidence_key,
                {"scale":"", "note":"Aucun résultat exploitable détecté dans le document.",
                 "rows":[], "profile_code":"", "status":"REEL"})
        if code == "PREFERENCES_PRO":
            data["dimensions"] = analysis["preference_dimensions"]
        sources[code] = data
    create_questionnaire_v2(ctx, case_id, sources, context="AUTRE", intro="",
                             expected_row_version=view.row_version)
    return len(analysis["ideas"])


def _lines(raw):
    return list(dict.fromkeys(v.strip() for v in raw.splitlines() if v.strip()))


def _setup_page_nav(case_id, prefix, pages):
    import streamlit as st
    selected=st.radio("Navigation", list(pages), horizontal=True, key=f"{prefix}_nav_{case_id}")
    return selected


def _save_questionnaire_change(ctx, case_id, view, current, candidate):
    """Persist a valid coach edit before navigation can discard its widgets."""
    import streamlit as st
    if candidate == current:
        return False
    try:
        save_questionnaire(ctx, case_id, candidate, expected_row_version=view.row_version)
        st.session_state[f"rc3_q_saved_{case_id}"] = True
        st.caption("Modification enregistrée sur le serveur. Vous pouvez poursuivre ou revenir aux autres étapes.")
    except Exception as exc:
        st.warning("Cette modification n’est pas encore enregistrée. La dernière version valide reste sur le serveur; corrigez le champ avant de quitter cette étape.")
        _err(exc)
    return True


def _preview_questionnaire(q):
    """Même aperçu public avant et après validation ; aucune remarque privée."""
    import streamlit as st
    from clarte360_cp.domain.preparation_v2 import public_questionnaire_v2
    from clarte360_cp.ui.preparation_rc3b import (
        CAV1_MEANING_INSTRUCTION, CAV1_MORE_INFORMATION_LABEL, _STATUS, _evidence_box,
    )
    q=public_questionnaire_v2(q)
    st.write(q["intro"])
    st.markdown("### Partie 1 — Mes idées et pistes")
    if not q["ideas_active"]:
        st.write("Aucune piste proposée : le bénéficiaire pourra ajouter une idée ou confirmer qu'il n'a pas de piste aujourd'hui.")
    for idx,item in enumerate(q["ideas_active"],1):
        with st.expander(f"Piste {idx} — {item['wording']} : toutes les questions",expanded=True):
            st.markdown("**1. Souhaitez-vous encore explorer cette piste ?**")
            st.write(" / ".join(_STATUS[x] for x in INTEREST_CHOICES))
            st.caption("Les questions suivantes restent disponibles tant que la piste n'est pas explicitement écartée.")
            for label,opts in (("2. Que représente cette idée pour vous ?",CAV1_MEANINGS),
                              ("3. Dans quel cadre pourriez-vous envisager cette activité ?",CAV1_STATUSES),
                              ("4. Qu'est-ce qui vous attire dans cette piste ?",CAV1_ATTRACTIONS),
                              ("5. Qu'avez-vous déjà vérifié à son sujet ?",CAV1_ACCESS)):
                st.markdown("**"+label+"**")
                st.caption(CAV1_MEANING_INSTRUCTION if opts is CAV1_MEANINGS
                           else "Vous pouvez sélectionner plusieurs réponses.")
                st.write(" · ".join(opts))
            st.markdown("**6. Y a-t-il un contexte particulier d'exercice ?**")
            st.write(item["context_prompt"])
            st.caption("Cadre ou contexte envisagé — plusieurs réponses possibles : "+" · ".join(item["context_choices"]))
            st.markdown("**"+CAV1_MORE_INFORMATION_LABEL+" (facultatif)**")
            st.caption("Zone de saisie libre située en bas de cette fiche, pour préciser cette piste ou son contexte.")
            st.markdown("**Une autre précision à apporter ? (facultatif)**")
    if q["enterprise_wording"]:
        st.markdown("### Perspective évoquée par mon entreprise — distincte de mes idées")
        st.write(q["enterprise_wording"])
        st.caption("Le bénéficiaire conserve son choix personnel concernant cette perspective.")
    st.markdown("### Partie 2 — Mes repères personnels")
    for code in ("valeurs","moteurs","preferences"):
        cfg=q["cav2"][code]
        st.write("**"+code.title()+" :** "+cfg["question"])
        if code in ("valeurs","moteurs"):
            st.caption("Jusqu'à trois choix personnels : "+(" · ".join(cfg["choices"]) if cfg["mode"]=="CHOIX" else "Expression libre si le rapport manque"))
        else:
            st.caption("Jusqu'à trois dimensions prioritaires : "+(" · ".join(d["label"] for d in cfg["dimensions"]) if cfg["mode"]=="DIMENSIONS" else "Expression libre si le rapport manque"))
            st.caption("Pour chaque dimension retenue : mode souhaité, indispensable ou adaptable et nuance facultative.")
            st.write("**Condition difficile à accepter :** "+cfg["situation_question"])
    st.markdown("#### Lire les résultats précédents sans refaire les tests")
    for nm,title in (("valeurs","Boussole et cotations d'incarnation"),("moteurs","Moteurs et indices"),("preferences","Préférences et deux pôles"),("ipip","IPIP-NEO-120"),("pip","PIP RIASEC")):
        _evidence_box(q,nm,title=title)
    st.caption("Les liens directs vers les rapports seront fournis via le Hub lorsque le connecteur sera disponible.")


def render_builder(ctx, case_id):
    import streamlit as st
    view=read_preparation(ctx,case_id)
    gate=_current_document_gate(ctx,case_id)
    pending=gate["pending"]
    verified_sources=gate["verified_sources"]
    st.title("Préparer le questionnaire du bénéficiaire")
    st.caption("Vous préparez les deux parties avant de les mettre à disposition du bénéficiaire.")
    if st.session_state.pop(f"gda_cp_documents_saved_{case_id}", False):
        st.success("Les sept choix ont été enregistrés ensemble et le brouillon est ouvert ci-dessous. Vous n’avez pas à re-sélectionner les pièces.")
    analyzed_ideas = st.session_state.pop(f"rc3_source_analysis_success_{case_id}", None)
    if analyzed_ideas is not None:
        st.success(f"Brouillon enregistré : {analyzed_ideas} piste(s) issue(s) de l’APS, questions de contexte et repères préparés depuis les pièces retenues. Vérifiez le contenu avant publication.")
    extra_analysis = st.session_state.get(f"gda_d5_optional_ai_result_{case_id}")
    if extra_analysis:
        with st.expander("Analyse IA de la pièce complémentaire à examiner", expanded=True):
            st.markdown(f"**Pièce :** {extra_analysis.get('document_name', 'Document complémentaire')}")
            st.markdown(f"**Influence possible : {extra_analysis.get('pertinent', 'À vérifier')}** — {extra_analysis.get('motif', '')}")
            if extra_analysis.get("elements_utiles"):
                st.markdown("**Éléments à examiner**")
                for line in extra_analysis["elements_utiles"]:
                    st.markdown(f"- {line}")
            if extra_analysis.get("pistes_questionnaire"):
                st.markdown("**Pistes de questions, à valider par l’intervenant**")
                for line in extra_analysis["pistes_questionnaire"]:
                    st.markdown(f"- {line}")
            if extra_analysis.get("limites"):
                st.caption("Limites : " + " · ".join(extra_analysis["limites"]))
            st.caption("L’analyse n’ajoute aucune réponse et ne modifie pas seule le questionnaire.")
    st.info("Vous pourrez modifier les questions et revenir aux étapes précédentes jusqu’à la publication. La publication verrouille cette version du questionnaire.")
    if st.session_state.pop(f"rc3_q_saved_{case_id}", False):
        st.success("Modification du questionnaire enregistrée sur le serveur.")
    if view.questionnaire and not view.questionnaire_locked and not view.questionnaire.get("ideas_active"):
        with st.expander("Le brouillon actuel ne contient aucune piste APS", expanded=True):
            st.caption("Reprenez le brouillon depuis les pièces retenues. Cette action crée une nouvelle version et conserve l’historique; les rapprochements ne sont pas à refaire.")
            with st.form(f"rc3_regenerate_sources_{case_id}"):
                observation = st.text_area("Observation privée de l’intervenant (facultatif)", max_chars=380,
                    key=f"rc3_regenerate_observation_{case_id}",
                    help="Elle aide à formuler la question de contexte. Elle reste une hypothèse de l’intervenant, jamais une réponse attribuée au bénéficiaire.")
                consent = st.checkbox(
                    "J’ai informé le bénéficiaire et il consent à l’analyse temporaire par l’IA des pièces retenues afin de préparer le brouillon du questionnaire.",
                    key=f"rc3_regenerate_source_consent_{case_id}")
                regenerate = st.form_submit_button("Créer une nouvelle version depuis les pièces", type="primary", disabled=not consent)
            if regenerate:
                from clarte360_cp.connectors.cav3_ai import Cav3AIError
                from clarte360_cp.connectors.gda_documents import GDAError
                try:
                    with st.spinner("Lecture temporaire et analyse des pièces retenues…"):
                        ideas_count = _create_questionnaire_from_documents(ctx, case_id, view, verified_sources, observation)
                    st.session_state[f"rc3_source_analysis_success_{case_id}"] = ideas_count
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc) if isinstance(exc, (Cav3AIError, GDAError, ValueError, PermissionError)) else "L’analyse n’a pas abouti. Aucun nouveau questionnaire vide n’a été enregistré; votre version actuelle et les choix de documents sont conservés.")
    if view.questionnaire and not (view.questionnaire_locked and view.invitation_open) and (gate.get("error") or pending):
        st.warning("L’envoi est suspendu : le dossier documentaire doit être à jour avant de verrouiller cette version.")
        if gate.get("error"):
            st.error(gate["error"])
        for item in pending:
            st.write("• " + item)
        if st.button("Ouvrir Documents pour terminer",type="primary"):
            from clarte360_cp.framework.navigation import set_page
            set_page(st.session_state,"documents")
            st.rerun()
        return
    with st.popover("ⓘ Comment préparer le questionnaire ?"):
        st.write("1. Les pièces retenues dans Documents sont reprises comme sources. 2. Reportez les éléments utiles dans le brouillon. 3. Relisez les questions et les repères personnels. 4. Prévisualisez tout, puis publiez le questionnaire.")
        st.caption("Les sources d’origine restent conservées. Après publication, cette version ne peut plus être modifiée.")
    if not view.questionnaire:
        from clarte360_cp.ui.preparation import SOURCE_LABELS
        if gate.get("error"):
            st.error("La préparation est suspendue : " + gate["error"])
            if st.button("Ouvrir Documents pour rétablir l’accès aux pièces"):
                from clarte360_cp.framework.navigation import set_page
                set_page(st.session_state,"documents")
                st.rerun()
            return
        if pending:
            st.warning(f"Avant de commencer, traitez dans Documents les {len(pending)} pièce(s) encore en attente. Rapprochez-les, vérifiez-les ou indiquez qu’elles ne seront pas utilisées.")
            for item in pending:
                st.write("• " + item)
            if st.button("Ouvrir Documents pour terminer la vérification",type="primary"):
                from clarte360_cp.framework.navigation import set_page
                set_page(st.session_state,"documents")
                st.rerun()
            return
        auto_key = f"gda_cp_autocreate_questionnaire_{case_id}"
        if st.session_state.get(auto_key):
            st.subheader("Créer le questionnaire à partir des pièces retenues")
            st.info("C&P va lire temporairement les pièces GDA retenues, préparer les pistes et les repères réellement présents dans les rapports, puis enregistrer un brouillon à relire. Rien n’est publié ni envoyé au bénéficiaire à cette étape.")
            st.caption("Le texte extrait est envoyé au service IA Clarté360 configuré pour l’application. L’appel utilise store=false; C&P ne conserve pas le texte extrait après l’analyse. Une lecture humaine et une validation restent obligatoires avant publication.")
            with st.form(f"rc3_source_analysis_consent_{case_id}"):
                observation = st.text_area("Observation privée de l’intervenant (facultatif)", max_chars=380,
                    key=f"rc3_source_observation_{case_id}",
                    help="Elle aide à formuler la question de contexte. Elle reste une hypothèse de l’intervenant, jamais une réponse attribuée au bénéficiaire.")
                consent = st.checkbox(
                    "J’ai informé le bénéficiaire et il consent à l’analyse temporaire par l’IA des pièces retenues afin de préparer le brouillon du questionnaire.",
                    key=f"rc3_source_analysis_consent_{case_id}")
                analyze = st.form_submit_button("Analyser les pièces et créer le brouillon", type="primary", disabled=not consent)
            if analyze:
                try:
                    from clarte360_cp.connectors.cav3_ai import Cav3AIError
                    from clarte360_cp.connectors.gda_documents import GDAError
                    with st.spinner("Lecture temporaire et analyse des pièces retenues…"):
                        ideas_count = _create_questionnaire_from_documents(ctx, case_id, view, verified_sources, observation)
                    st.session_state[auto_key] = False
                    st.session_state[f"gda_cp_documents_saved_{case_id}"] = True
                    st.session_state[f"rc3_source_analysis_success_{case_id}"] = ideas_count
                    st.rerun()
                except Exception as exc:
                    from clarte360_cp.connectors.cav3_ai import Cav3AIError
                    from clarte360_cp.connectors.gda_documents import GDAError
                    st.error(str(exc) if isinstance(exc, (Cav3AIError, GDAError, ValueError, PermissionError)) else "L’analyse n’a pas abouti. Aucun brouillon vide n’a été enregistré; vos choix de documents sont conservés.")
            return
        st.subheader("Étape 1 — Préparer un brouillon à partir des pièces vérifiées")
        st.info("Le brouillon est créé directement à partir des choix enregistrés dans Documents. Il n’est pas envoyé : relisez-le, ajustez-le et prévisualisez-le avant sa publication dans l’espace bénéficiaire.")
        if verified_sources:
            st.caption(f"{len(verified_sources)} pièce(s) retenue(s) dans Documents sont reprises automatiquement comme sources. Vous n’avez pas à les sélectionner une seconde fois.")
        elif not gate.get("has_inventory"):
            st.warning("Aucune pièce vérifiée n’est reliée à ce dossier. Vous pouvez préparer le questionnaire sans source documentaire, à partir des échanges du bilan, après confirmation ci-dessous.")
        with st.form("rc3_generate"):
            context=st.selectbox("Contexte contractuel",list(CONTEXTS),format_func=lambda x:CONTEXT_LABELS[x])
            intro=st.text_area("Introduction destinée au bénéficiaire (modifiable)",value="Lors de votre APS et/ou au cours de votre parcours, certaines envies ou pistes ont peut-être émergé. Ce questionnaire vous aide à préciser ce que vous souhaitez explorer, sans imposer de métier. Vous pourrez modifier vos réponses jusqu'à leur validation définitive.")
            no_source_confirmed=True
            if not gate.get("has_inventory") and not verified_sources:
                no_source_confirmed=st.checkbox("J’ai vérifié qu’aucune pièce n’est à rapprocher et je poursuis sans source documentaire.",key=f"rc3_no_sources_{case_id}")
            submit=st.form_submit_button("Commencer le brouillon du questionnaire",type="primary",disabled=not no_source_confirmed)
            if submit:
                sources={}
                for code, purpose in (("APS_OBJECTIF","APS_OBJECTIF"),("BOUSSOLE_VALEURS","BOUSSOLE_VALEURS"),
                                      ("MOTEURS_PRO","MOTEURS_PRO"),("PREFERENCES_PRO","PREFERENCES_PRO"),
                                      ("IPIP_REPORT","IPIP_REPORT"),("PIP_REPORT","PIP_REPORT")):
                    record=verified_sources.get(purpose)
                    if record:
                        doc=record["document"]
                        data={"authorized":True,"source_ref":doc.source_ref,"label":SOURCE_LABELS[code]}
                        if code in ("IPIP_REPORT","PIP_REPORT"):data["status"]="REEL"
                        sources[code]=data
                try:create_questionnaire_v2(ctx,case_id,sources,context=context,intro=intro,expected_row_version=view.row_version);st.rerun()
                except Exception as exc:_err(exc)
        return
    q=view.questionnaire
    if view.questionnaire_locked:
        st.success(f"Questionnaire verrouillé — version {view.questionnaire_version}.")
        if not view.invitation_open:
            st.warning("Le questionnaire est verrouillé mais pas encore disponible pour le bénéficiaire.")
            if st.button("Envoyer dans l’espace bénéficiaire",type="primary"):
                try:open_beneficiary_access(ctx,case_id,expected_row_version=view.row_version);st.rerun()
                except Exception as exc:_err(exc)
        else: st.success("Questionnaire disponible dans l’espace bénéficiaire. Il pourra répondre puis transmettre une seule fois ses réponses. Aucun e-mail automatique n’est envoyé par D5.")
        st.subheader("Contenu approuvé — aperçu des questions")
        st.caption("Voici les formulations enregistrées dans le questionnaire validé. Les remarques privées de l'accompagnateur ne sont pas affichées au bénéficiaire. Ce contenu verrouillé ne peut plus être modifié ici.")
        _preview_questionnaire(q)
        return
    step=_setup_page_nav(case_id,"rc3_coach",("1. Préparer les idées et pistes", "2. Préparer les repères personnels", "3. Prévisualiser le questionnaire", "4. Publier le questionnaire"))
    if step.startswith("1."):
        st.subheader("Partie 1 — Examiner les idées, une piste à la fois")
        st.caption("L'exclusion du questionnaire ne supprime jamais la source APS. La question de contexte reste disponible pour chaque piste active.")
        st.info("Chaque modification est enregistrée sur le serveur. Vous pouvez passer aux autres étapes et revenir ici. Relisez l’aperçu complet avant de publier.")
        st.markdown("**Pistes actives**")
        for idea in q["ideas_active"]:
            st.write(f"• {idea['wording']} ({idea['origin']})")
        with st.form("rc3_add_idea"):
            label=st.text_input("Ajouter une piste nouvelle, même absente des documents",max_chars=300)
            if st.form_submit_button("Ajouter cette piste"):
                if label.strip():
                    n=copy.deepcopy(q);item=new_idea(label.strip(),"ECHANGES_ACCOMPAGNATEUR")
                    if item["id"] not in {v["id"] for v in n["ideas_active"]}:
                        n["ideas_active"].append(item)
                    try:
                        save_questionnaire(ctx,case_id,n,expected_row_version=view.row_version)
                        st.session_state[f"rc3_idea_added_{case_id}"] = True
                        st.rerun()
                    except Exception as exc:_err(exc)
        if st.session_state.pop(f"rc3_idea_added_{case_id}", False):
            st.success("Piste enregistrée dans le brouillon. Elle apparaît ci-dessous et sera incluse dans l’aperçu.")
        if q["ideas_active"]:
            names={x["id"]:x["wording"] for x in q["ideas_active"]}
            which=st.selectbox("Examiner les questions d'une seule piste",list(names),format_func=lambda x:names[x])
            item=next(x for x in q["ideas_active"] if x["id"]==which)
            st.markdown(f"### Piste : {item['wording']}")
            st.caption("Libellé d’origine conservé : " + (item["source_wording"] or "piste ajoutée en entretien"))
            st.caption("Questions 1 à 5 communes à chaque piste : intérêt actuel, sens de l'idée, cadre envisagé, éléments attirants et conditions vérifiées. La question 6 ci-dessous permet de personnaliser le contexte de cette piste.")
            edited=copy.deepcopy(item)
            prefix=f"rc3_edit_{case_id}_{which}_{view.questionnaire_version}"
            edited["wording"]=st.text_input("Libellé présenté au bénéficiaire",value=st.session_state.get(prefix+"_wording",item["wording"]),key=prefix+"_wording")
            observation=st.text_area("Remarque privée de l'accompagnateur — non visible par le bénéficiaire",value=st.session_state.get(prefix+"_note",item["context_note"]),key=prefix+"_note")
            st.caption("Cette remarque reste dans votre espace. Pour poser une question au bénéficiaire, utilisez le champ Question 6 ci-dessous.")
            edited["context_prompt"]=st.text_area("Question 6 — contexte d'exercice, visible par le bénéficiaire",value=st.session_state.get(prefix+"_prompt",item["context_prompt"]),height=125,key=prefix+"_prompt")
            options=st.text_area("Réponses proposées à la question 6 (une par ligne)",value=st.session_state.get(prefix+"_options","\n".join(item["context_choices"])),height=180,key=prefix+"_options")
            edited["context_note"]=observation
            edited["context_choices"]=_lines(options)
            choice=st.radio("Traitement",("CONSERVER","EXCLURE DU QUESTIONNAIRE"),horizontal=True,key=prefix+"_treatment")
            st.caption("Vos modifications valides sont enregistrées sur le serveur. L’exclusion reste une action explicite et conserve la piste dans les archives.")
            n=copy.deepcopy(q)
            if choice=="CONSERVER":
                n["ideas_active"]=[edited if x["id"]==which else x for x in n["ideas_active"]]
            s1=st.button("Appliquer l’exclusion de cette piste",key=prefix+"_exclude",type="secondary",disabled=choice!="EXCLURE DU QUESTIONNAIRE")
            s2=st.button("Proposer une adaptation à partir de ma remarque",key=prefix+"_suggest")
            if choice=="CONSERVER":
                _save_questionnaire_change(ctx,case_id,view,q,n)
            if s1:
                n=copy.deepcopy(q)
                n["ideas_active"]=[x for x in n["ideas_active"] if x["id"]!=which]
                n["ideas_archived"].append(edited)
                _save_questionnaire_change(ctx,case_id,view,q,n)
            if s2:
                try:
                    proposed=adapt_context_question(item,observation)
                    st.session_state[f"rc3_suggest_{which}"]=proposed["context_prompt"]
                    st.rerun()
                except Exception as exc:_err(exc)
            suggested=st.session_state.get(f"rc3_suggest_{which}")
            if suggested:
                st.markdown("**Comparer avant/après**")
                st.write("Avant : " + item["context_prompt"])
                st.write("Proposition : " + suggested)
                col1,col2=st.columns(2)
                if col1.button("Accepter cette question",key=f"accept_{which}"):
                    n=copy.deepcopy(q)
                    for p in n["ideas_active"]:
                        if p["id"]==which:
                            p["context_prompt"]=suggested
                            p["context_note"]=observation
                    try:save_questionnaire(ctx,case_id,n,expected_row_version=view.row_version);del st.session_state[f"rc3_suggest_{which}"];st.rerun()
                    except Exception as exc:_err(exc)
                if col2.button("Refuser cette question",key=f"decline_{which}"):
                    del st.session_state[f"rc3_suggest_{which}"];st.rerun()
        if q["ideas_archived"]:
            st.caption("Pistes écartées du questionnaire (sources conservées) : " + ", ".join(i["wording"] for i in q["ideas_archived"]))
    elif step.startswith("2."):
        st.subheader("Partie 2 — Préparer les repères personnels")
        st.caption("Les résultats sourcés facilitent la lecture mais ne déterminent jamais les choix. Aucun mini-test PIP/NEO n'est ajouté.")
        with st.popover("ⓘ Comprendre les trois familles de repères"):
            st.write("Valeurs : incarnation dans la Boussole ≠ importance future. Moteurs : sources de motivation déclarées ≠ capacités. Préférences : positions entre deux pôles ≠ compétences. Le bénéficiaire sélectionnera lui-même ses priorités.")
        from clarte360_cp.ui.preparation_rc3b import _evidence_box
        for nm,title in (("valeurs","Boussole : résultats et définitions"),("moteurs","Moteurs : résultats et définitions"),("preferences","Préférences : résultats et continuums"),("ipip","IPIP-NEO-120 : aperçu du rapport"),("pip","PIP RIASEC : aperçu du rapport")):
            _evidence_box(q,nm,title=title)
        n=copy.deepcopy(q)
        prefix=f"rc3_cav2_{case_id}_{view.questionnaire_version}"
        n["intro"]=st.text_area("Texte d'introduction commun aux deux parties",value=q["intro"],height=130,key=prefix+"_intro")
        for code in ("valeurs","moteurs"):
            sec=n["cav2"][code]
            st.markdown(f"#### {code.title()} — au maximum 3 priorités")
            sec["question"]=st.text_area(f"Question {code}",value=q["cav2"][code]["question"],key=prefix+f"_{code}_question")
            st.caption("Questions libres si le rapport manque ; sinon options réelles du document autorisé.")
            if sec["mode"]=="CHOIX":
                sec["choices"]=_lines(st.text_area(f"Options proposées ({code})",value="\n".join(q["cav2"][code]["choices"]),height=130,key=prefix+f"_{code}_choices"))
            sec["note_prompt"]=st.text_input(f"Observation facultative {code}",value=q["cav2"][code]["note_prompt"],key=prefix+f"_{code}_note")
        pp=n["cav2"]["preferences"]
        st.markdown("#### Préférences — dix continuums, aucun GO/NO GO artificiel")
        pp["question"]=st.text_area("Question principale Préférences",value=q["cav2"]["preferences"]["question"],key=prefix+"_preferences_question")
        if pp["mode"]=="DIMENSIONS":
            for dim in pp["dimensions"]:
                st.caption(dim["label"]+" : "+dim["pole_1"]+" ↔ "+dim["pole_2"])
        else: st.info("Rapport absent ou continuums non vérifiés : question libre, aucune modalité de test inventée.")
        pp["situation_question"]=st.text_area("Question distincte sur les situations à éviter",value=q["cav2"]["preferences"]["situation_question"],key=prefix+"_preferences_situation")
        _save_questionnaire_change(ctx,case_id,view,q,n)
    elif step.startswith("3."):
        st.subheader("Prévisualiser le questionnaire complet")
        st.caption("Vérifiez l’ordre et les formulations tels que le bénéficiaire les verra. Les remarques privées ne lui sont pas transmises. Les modifications sont enregistrées au fil des champs.")
        _preview_questionnaire(q)
    else:
        st.subheader("Publier le questionnaire")
        st.warning("L’envoi verrouille cette version et la rend accessible au bénéficiaire dans D5. Relisez les deux parties avant de continuer ; vous ne pourrez plus modifier cette version.")
        st.caption("Vérifiez les questions et réponses proposées dans l’aperçu, y compris la question de contexte de chaque piste.")
        st.write(f"{len(q['ideas_active'])} piste(s) conservée(s), {len(q['ideas_archived'])} écartée(s). Les trois familles de repères sont configurées.")
        confirm=st.checkbox("J’ai relu le questionnaire complet et je confirme sa publication.")
        if st.button("Envoyer au bénéficiaire dans D5 et verrouiller",disabled=not confirm,type="primary"):
            try:lock_and_publish_questionnaire(ctx,case_id,expected_row_version=view.row_version);st.rerun()
            except Exception as exc:_err(exc)


def _av1_form(q,a,prefix):
    from clarte360_cp.ui.preparation_rc3b import render_av1
    return render_av1(q,a,prefix)


def _av2_form(q,a,prefix):
    from clarte360_cp.ui.preparation_rc3b import render_av2
    return render_av2(q,a,prefix)


def render_beneficiary(ctx,case_id):
    import streamlit as st
    from clarte360_cp.application.orientation import OrientationConflict
    from clarte360_cp.ui.preparation_draft import get_draft, prepare_draft, save_draft, reload_draft
    from clarte360_cp.ui.preparation_rc3b import apply_ui_style
    apply_ui_style()
    view=read_preparation(ctx,case_id)
    st.title("Explorer mes idées et mes repères")
    if not view.questionnaire:
        st.info("Votre accompagnateur prépare votre questionnaire. Il sera proposé ici dès qu'il l'aura approuvé.")
        return
    q=view.questionnaire
    st.write(q["intro"])
    st.caption("Deux parties à remplir une seule fois. Votre brouillon est enregistré sur le serveur pendant la saisie. Aucun conseil ni interprétation automatique n’est produit pendant vos réponses.")
    if view.active_answers is not None:
        st.success("Vos réponses ont été envoyées définitivement. Merci !")
        st.caption("Cet envoi est irréversible. Vous ne pouvez plus modifier ces réponses dans votre espace. Si une correction est nécessaire, vous pourrez la préparer avec votre accompagnateur en séance. La version envoyée restera conservée en lecture seule.")
        with st.expander("Rappel des réponses transmises",expanded=False):
            a=view.active_answers
            for idea in a["cav1"]["ideas"]:
                wording=next((p["wording"] for p in q["ideas_active"] if p["id"]==idea["id"]),"Une piste")
                st.write("**"+wording+" :** "+STATUS_LABELS.get(idea["interest"],idea["interest"]))
            for code in ("valeurs","moteurs"):
                z=a["cav2"][code];st.write("**"+code.capitalize()+" :** "+", ".join(z["choices"] or z["free"]) if z["choices"] or z["free"] else "**"+code.capitalize()+" :** Aucune priorité retenue")
        return
    if not ctx.has_scope("CP_BENEFICIARY_INTERACT"):
        st.warning("Votre accès actuel permet la lecture mais pas la saisie.")
        return
    buffer=get_draft(st.session_state,case_id,view)
    data=buffer.answers
    step_key=f"rc3_step_{case_id}_{view.questionnaire_version}"
    confirm_key=f"rc3_benef_confirm_{case_id}"
    if step_key not in st.session_state:
        st.session_state[step_key]=2 if data["cav1_done"] else 1
    step=st.session_state[step_key]
    if buffer.conflict:
        st.session_state[confirm_key]=False
        st.error(buffer.conflict_message)
        st.caption("La sauvegarde est suspendue dans cette fenêtre. Recharger remplacera la saisie affichée par la dernière version enregistrée.")
        if st.button("Recharger les réponses enregistrées",key=f"rc3_reload_{case_id}"):
            reload_draft(st.session_state,case_id,view)
            st.rerun()
    st.progress(0.50 if step==1 else 1.0,text=f"Partie {step} sur 2")
    if not buffer.conflict:
        st.caption("Votre brouillon est enregistré quand vous changez un choix ou quittez une zone de texte. Les boutons de fin d'étape confirment que vous avez terminé la partie concernée.")
    back=False
    continue_next=False
    if step==1:
        st.session_state[confirm_key]=False
        answers=_av1_form(q,data,f"B_{case_id}")
        col1,col2=st.columns(2)
        save=col1.button("Enregistrer mon brouillon",key=f"rc3_benef_cav1_draft_{case_id}",disabled=buffer.conflict)
        continue_next=col2.button("Terminer cette partie et continuer →",type="primary",key=f"rc3_benef_cav1_next_{case_id}",disabled=buffer.conflict)
        complete=True if continue_next else False if save else None
    else:
        # Le retour est traité après lecture/sauvegarde des champs C-AV2 :
        # un dernier texte saisi au moment du clic ne doit pas être perdu.
        back=st.button("← Revenir à mes idées",key=f"rc3_back_{case_id}",disabled=buffer.conflict)
        answers=_av2_form(q,data,f"B_{case_id}")
        col1,col2=st.columns(2)
        save=col1.button("Enregistrer mon brouillon",key=f"rc3_benef_cav2_draft_{case_id}",disabled=buffer.conflict)
        finish=col2.button("Terminer cette partie",type="primary",key=f"rc3_benef_cav2_done_{case_id}",disabled=buffer.conflict)
        complete=True if finish else False if save else None
    saved_ok=False
    changed=False
    if not buffer.conflict:
        try:
            candidate=prepare_draft(buffer,q,answers,part=step,complete=complete)
            changed=candidate!=buffer.answers
            if changed or complete is not None:
                st.session_state[confirm_key]=False
            saved=save_draft(st.session_state,ctx,case_id,view,candidate)
            buffer=get_draft(st.session_state,case_id,saved)
            saved_ok=True
        except OrientationConflict:
            st.session_state[confirm_key]=False
            # Le helper mémorise le conflit : un seul rerun pour afficher sa
            # reprise en haut de page, puis aucune nouvelle tentative d'écriture.
            st.rerun()
        except Exception as exc:
            st.session_state[confirm_key]=False
            st.error("Ces dernières modifications n'ont pas pu être enregistrées. Elles restent affichées dans cette fenêtre.")
            _err(exc)
    if saved_ok:
        if changed or save:
            st.caption("Brouillon enregistré.")
        if continue_next or back:
            st.session_state[confirm_key]=False
            st.session_state[step_key]=2 if continue_next else 1
            st.rerun()
        if step==2 and buffer.answers["cav1_done"] and buffer.answers["cav2_done"]:
            st.divider()
            st.markdown("### Vérifier avant l’envoi")
            st.warning("Après l’envoi définitif, vous ne pourrez plus modifier ces réponses vous-même. Une éventuelle correction se fera avec votre accompagnateur en séance. Vos réponses envoyées resteront conservées en lecture seule.")
            confirm=st.checkbox("J’ai relu mes deux parties et je confirme l’envoi définitif de mes réponses.",key=confirm_key)
            if st.button("Envoyer mes réponses définitivement",
                disabled=not confirm or not ctx.has_scope("CP_BENEFICIARY_VALIDATE"),
                type="primary",key=f"rc3_benef_submit_{case_id}"):
                try:submit_beneficiary_answers(ctx,case_id,expected_row_version=buffer.row_version);st.rerun()
                except Exception as exc:_err(exc)
        elif step==2:
            st.session_state[confirm_key]=False
        st.caption("Votre brouillon est sauvegardé sur le serveur après chaque changement ou sortie de champ. Cliquez sur « Terminer cette partie » lorsque vous avez fini.")
    st.caption("Les modifications sont sauvegardées sur le serveur après chaque choix ou sortie de champ. Vous pouvez quitter cette page puis reprendre le brouillon. Avant de fermer, vérifiez le message d’enregistrement et l’absence d’erreur.")


def render_review(ctx,case_id):
    import streamlit as st
    from clarte360_cp.ui.preparation_rc3b import apply_ui_style
    apply_ui_style()
    view=read_preparation(ctx,case_id)
    st.title("Relire les réponses avec le bénéficiaire")
    st.caption("À faire en séance ou en partage d’écran. Le questionnaire n’est pas renvoyé. Les réponses déjà envoyées restent conservées. Les changements sont enregistrés sur le serveur après chaque choix ou sortie de zone de texte.")
    if view.active_answers is None:
        st.info("La relecture pourra commencer lorsque le bénéficiaire aura envoyé définitivement ses réponses.")
        return
    st.info(f"Version des réponses : {view.active_response_version}. Les réponses d’origine restent conservées. Vos corrections sont sauvegardées sur le serveur au fil des changements. Seule la confirmation commune crée une nouvelle version de référence.")
    base=view.joint_draft or view.active_answers
    tab1,tab2=st.tabs(["Partie 1 — Idées et pistes","Partie 2 — Repères personnels"])
    with tab1:
        revised1=_av1_form(view.questionnaire,base,f"J_{case_id}_1")
        finish_cav1=st.button("Terminer les corrections de cette partie",key=f"rev1_{case_id}")
    with tab2:
        revised2=_av2_form(view.questionnaire,base,f"J_{case_id}_2")
        finish_cav2=st.button("Terminer les corrections de cette partie",key=f"rev2_{case_id}",disabled=not base.get("cav1_done",False))
    candidate=copy.deepcopy(base)
    candidate["cav1"]=copy.deepcopy(revised1["cav1"])
    candidate["cav2"]=copy.deepcopy(revised2["cav2"])
    changed_cav1=candidate["cav1"]!=base["cav1"]
    changed_cav2=candidate["cav2"]!=base["cav2"]
    if changed_cav1:
        candidate["cav1_done"]=False
        candidate["cav2_done"]=False
    if changed_cav2:
        candidate["cav2_done"]=False
    if finish_cav1:
        candidate["cav1_done"]=True
        candidate["cav2_done"]=False
    if finish_cav2:
        candidate["cav2_done"]=True
    if changed_cav1 or changed_cav2 or finish_cav1 or finish_cav2:
        try:
            view=save_joint_review(ctx,case_id,candidate,expected_row_version=view.row_version)
            st.caption("Correction enregistrée sur le serveur.")
        except Exception as exc:
            st.error("La dernière correction n’a pas été enregistrée. Elle reste affichée dans cette session; réessayez ou rechargez avant de quitter.")
            _err(exc)
    if view.joint_draft:
        with st.expander("Voir les modifications avant de les revalider",expanded=True):
            st.json(difference(view.active_answers,view.joint_draft),expanded=False)
        st.warning("Les réponses envoyées à l’origine restent intactes. La confirmation commune établit une nouvelle version de référence. Une correction ultérieure créera une autre version, sans modifier les précédentes.")
    if view.reviewed_in_session and not view.joint_draft:
        st.success("Relecture validée conjointement ; version courante disponible pour la suite.")
    else:
        st.warning("La confirmation commune établira cette version comme nouvelle référence. Les réponses d’origine resteront conservées en lecture seule. Toute correction ultérieure créera une autre version.")
        import hashlib, json
        confirmation_fingerprint=hashlib.sha256(json.dumps(candidate,ensure_ascii=False,sort_keys=True).encode("utf-8")).hexdigest()[:12]
        confirmed=st.checkbox("Le bénéficiaire a relu et confirmé cette version dans cet écran partagé.",key=f"joint_confirm_{case_id}_{confirmation_fingerprint}")
        method=st.radio("Modalité",["PARTAGE_ECRAN_ORAL","EN_SEANCE_PRESENTIEL"])
        complete=bool(base.get("cav1_done") and base.get("cav2_done"))
        if not complete:
            st.caption("Terminez et enregistrez d’abord les deux parties du questionnaire.")
        if st.button("Confirmer notre relecture commune",disabled=not confirmed or not complete,type="primary"):
            try:confirm_joint_review(ctx,case_id,beneficiary_confirmed=True,method=method,expected_row_version=view.row_version);st.rerun()
            except Exception as exc:_err(exc)
    with st.expander("Historique des versions"):
        for row in response_history(ctx,case_id):
            if row["state"] in ("BENEFICIAIRE_VALIDE","REVUE_CONJOINTE"):
                state_label = "Envoyé par le bénéficiaire" if row["state"] == "BENEFICIAIRE_VALIDE" else "Relu ensemble"
                st.caption(f"{row['created_at']} — Version {row['no']} — {state_label}")


def render_cav3(ctx,case_id):
    import streamlit as st
    try:data=cav3_context(ctx,case_id)
    except Exception:
        st.info("La préparation de questions avec l’aide de l’IA sera disponible après l’envoi définitif des réponses.")
        return
    st.subheader("Préparer des questions d’entretien avec l’aide de l’IA")
    status_label = {
        "R2_BROUILLON_NON_VALIDE": "Corrections en cours, à confirmer en séance",
        "REVU_EN_SEANCE": "Réponses relues en séance",
        "PREPARATOIRE_NON_VALIDE": "Réponses envoyées, en attente de relecture",
    }.get(data["status"], "État à vérifier")
    st.caption(f"Réponses version {data['response_version']} · {status_label}. Travail réservé à l’accompagnateur. Aucune nouvelle passation n’est demandée au bénéficiaire.")
    r=data["reponses"]
    if r.get("schema")!="GO22_CAV1_CAV2_REPONSES_UNIQUES_V2":return
    st.write("**Idées que le bénéficiaire souhaite explorer :**", [x["wording"] for x in r["cav1"]["ideas"] if x["interest"]!="NON_ACTUELLEMENT"] or "Aucune direction imposée")
    for key in ("valeurs","moteurs"):
        block=r["cav2"][key]
        st.write(f"**{key.title()} retenus :**",block["choices"] or block["free"] or block["none_reason"] or "Aucun")
    st.write("**Nombre de préférences retenues :**", len(r["cav2"]["preferences"]["priorities"]))
    st.warning("Toute sortie IA reste une proposition interne à relire. Elle ne décide pas à la place de la personne et ne constitue ni diagnostic, ni score, ni recommandation de métier.")
    st.caption("La proposition IA utilise les réponses et références présentées ci-dessus. Elle reste à examiner par l’accompagnateur avec le bénéficiaire.")
    from clarte360_cp.application.preparation import run_cav3_analysis
    from clarte360_cp.connectors.cav3_ai import ai_ready
    configured = ai_ready()
    if not configured:
        st.info("Le secret IA partagé n'est pas disponible dans cette instance. L'historique et les réponses restent accessibles.")
    st.info("L’IA reçoit les réponses et les repères de sources affichés ci-dessus pour proposer des questions d’entretien. Le CV et les identifiants du dossier ne sont pas transmis. Le résultat est une proposition à relire, jamais une décision.")
    consented = st.checkbox(
        "Le bénéficiaire a été informé de cet envoi et l’accepte pour préparer l’entretien.",
        key=f"cav3_ai_consent_{case_id}_{data['source_fingerprint']}",
    )
    if st.button("Préparer les propositions de questions", type="primary", disabled=not configured or not consented):
        try:
            run_cav3_analysis(ctx, case_id)
            st.success("Les propositions sont enregistrées pour cette version des réponses.")
            st.rerun()
        except Exception as exc:
            _err(exc)
    try:
        from clarte360_cp.application.preparation import cav3_analysis_history
        history = cav3_analysis_history(ctx, case_id)
    except Exception:
        history = []
    for analysis in reversed(history):
        status = ("À confirmer avec le bénéficiaire" if analysis["current"] and analysis["source_stage"] == "R2_PROVISOIRE"
                  else "À examiner" if analysis["current"] else "Ancienne proposition — réponses ou sources modifiées")
        with st.expander(f"Propositions pour la version {analysis['response_version']} · {status} · {analysis['created_at']}", expanded=analysis["current"]):
            st.caption(f"Fournisseur : {analysis['provider']} · Modèle : {analysis['model']}")
            result = analysis["result"]
            metadata = result.get("_metadata", {})
            if metadata:
                st.caption(f"Consigne : {metadata.get('prompt_version')} · Empreinte de sortie : {metadata.get('output_hash')}")
            if not analysis["current"]:
                st.warning("Cette analyse concerne une ancienne version. Ne pas l'utiliser pour préparer ou valider les directions actuelles.")
            for item in result.get("directions", []):
                st.markdown("**Piste de discussion**")
                st.write(item["proposition"])
                st.caption("Éléments associés : " + ", ".join(map(str, item.get("evidence", []))))
                st.markdown("**Question possible en séance**")
                st.write(item["question_en_seance"])
            for item in result.get("points_a_eclaircir", []):
                st.markdown("**À éclaircir**")
                st.write(item["point"])
                st.caption(item["question_en_seance"])
            if result.get("incertitudes"):
                st.markdown("**Incertitudes signalées**")
                for item in result["incertitudes"]:
                    st.write("• " + item)
