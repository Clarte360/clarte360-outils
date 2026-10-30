"""GO22 RC2 - ecrans de recette pour questionnaire AV1/AV2, ZERO IA BENEFICIAIRE.

Pas de faux connecteur : la generation depuis les objets GDA et la distribution
SMTP necessitent encore le Hub. La preparation manuelle n'importe aucun PDF.
"""
from __future__ import annotations

import copy

from clarte360_cp.application.orientation import OrientationAccessDenied, OrientationConflict
from clarte360_cp.application.preparation import (
    cav3_context, confirm_joint_review, create_questionnaire,
    lock_questionnaire, open_beneficiary_access, read_preparation, response_history,
    save_beneficiary_answers, save_joint_review, save_questionnaire, submit_beneficiary_answers,
)
from clarte360_cp.domain.preparation import (
    CONTEXTS, ENTERPRISE_RESPONSES, SOURCES, empty_answers, valid_answers,
)
from clarte360_cp.framework.navigation import set_page

SOURCE_LABELS = {
    "CV_SOURCE": "CV", "APS_OBJECTIF": "APS initiale", "APS_P1": "APS renforcée", "BOUSSOLE_VALEURS": "Boussole des valeurs",
    "MOTEURS_PRO": "Moteurs professionnels", "PREFERENCES_PRO": "Préférences professionnelles",
    "IPIP_REPORT": "IPIP-NEO-120", "PIP_REPORT": "PIP RIASEC", "ENTREPRISE_PERSPECTIVE": "Perspective employeur autorisée",
}
NONE_LABELS = {"": "Choisir...", "AUCUN_CRITERE_IDENTIFIE": "Aucun critère indispensable identifié aujourd'hui", "A_AFFINER": "J'ai réfléchi mais je ne peux pas encore hiérarchiser"}


def _go(page: str) -> None:
    import streamlit as st
    set_page(st.session_state, page)
    st.rerun()


def _err(exc: Exception) -> None:
    import streamlit as st
    st.error(str(exc))


def _strings(raw: str, *, separator="\n") -> list[str]:
    return list(dict.fromkeys(v.strip() for v in raw.split(separator) if v.strip()))


def render_questionnaire_builder(ctx, case_id: str) -> None:
    import streamlit as st
    view = read_preparation(ctx, case_id)
    st.title("Préparer le questionnaire avant la séance")
    st.caption("Les questions sont préparées et relues avant leur mise à disposition au bénéficiaire.")
    st.info("Les sources doivent provenir du dossier autorisé. Cet ancien questionnaire utilise des références et libellés contrôlés : il n'importe pas automatiquement le contenu des documents partagés et n'envoie pas d'e-mail. Aucun document n'est copié dans le questionnaire.")
    if not view.questionnaire_locked:
        st.markdown("### 1. Générer depuis les sources disponibles")
        # Un st.expander dans un autre st.expander est interdit par Streamlit.
        with st.container():
            with st.form("prep_generate"):
                ctxt = st.selectbox("Cadre de financement", CONTEXTS, format_func=lambda v: {
                    "AUTOFINANCE": "Autofinancement", "ENTREPRISE_TRIPARTITE": "Entreprise / convention tripartite autorisée",
                    "ENTREPRISE_TRIPARTITE_MIXTE": "Entreprise / convention tripartite et cofinancement",
                    "FINANCEMENT_MIXTE": "Financement mixte sans perspective employeur autorisée", "AUTRE": "Autre dispositif",
                }[v])
                sources: dict = {}
                for code in SOURCES:
                    with st.expander(SOURCE_LABELS[code]):
                        enabled = st.checkbox("Source vérifiée et autorisée", key=f"prep_src_{code}")
                        ref = st.text_input("Référence de version dans le dossier", key=f"prep_ref_{code}", max_chars=240)
                        items = []
                        ideas = []
                        wording = ""
                        if code in {"APS_OBJECTIF", "APS_P1"}:
                            ideas = _strings(st.text_area("Idées explicitement citées (une par ligne, si présentes)", key=f"prep_ideas_{code}"))
                        elif code == "ENTREPRISE_PERSPECTIVE":
                            wording = st.text_area("Perspective explicitement autorisée (ne pas confondre avec un projet familial personnel)", key="prep_enterprise", max_chars=800)
                        elif code == "PREFERENCES_PRO":
                            items_go = _strings(st.text_area("Conditions recherchées (un pôle par ligne)", key="prep_items_pref_go"))
                            items_no_go = _strings(st.text_area("Situations à éviter (un pôle par ligne)", key="prep_items_pref_no_go"))
                        elif code != "MOTEURS_PRO":
                            items = _strings(st.text_area("Libellés exacts disponibles dans ce rapport (un par ligne)", key=f"prep_items_{code}"))
                        if enabled:
                            sources[code] = {"authorized": True, "source_ref": ref.strip(), "items": items,
                                             "idea_list": ideas, "wording": wording.strip()}
                            if code == "PREFERENCES_PRO":
                                sources[code]["items_go"] = items_go
                                sources[code]["items_no_go"] = items_no_go
                intro = st.text_area("Consigne introductive", max_chars=1400,
                                     value="Préparez vos idées et vos critères de travail. Il n'y a pas de bonne réponse : nous reprendrons ensemble vos choix lors du prochain entretien.")
                if st.form_submit_button("Créer le brouillon du questionnaire", type="primary"):
                    try:
                        create_questionnaire(ctx, case_id, sources, context=ctxt,
                                             intro=intro, expected_row_version=view.row_version)
                        st.rerun()
                    except (ValueError, OrientationConflict, OrientationAccessDenied) as exc:
                        _err(exc)
        if view.questionnaire:
            st.markdown("### 2. Prévisualisation et correction avant verrouillage")
            q = view.questionnaire
            with st.form("prep_review_q"):
                updated = copy.deepcopy(q)
                updated["intro"] = st.text_area("Message affiché avant les réponses", value=q["intro"], max_chars=1400)
                st.caption(f"Idées mentionnées dans l'APS (à confirmer librement) : {', '.join(q['aps_ideas']) or 'aucune'}")
                st.caption("Les rubriques et options ci-dessous restent modifiables avant verrouillage. Une formulation ajoutée par l'accompagnateur ne doit pas être attribuée faussement au rapport d'origine.")
                kept_sections = []
                for section in updated["sections"]:
                    with st.expander(f"{section['label']} — {section['max']} maximum"):
                        include = st.checkbox("Conserver cette rubrique", value=True, key=f"q_keep_{section['code']}")
                        section["question"] = st.text_area("Question", value=section["question"], max_chars=600,
                                                           key=f"q_title_{section['code']}")
                        edited_choices = st.text_area("Réponses proposées, une par ligne", value="\n".join(section["choices"]),
                                                      key=f"q_choices_{section['code']}")
                        section["choices"] = _strings(edited_choices)
                        if include:
                            kept_sections.append(section)
                updated["sections"] = kept_sections
                st.markdown("#### Questions fixes lorsqu'une idée professionnelle est citée")
                for key, label in (("meaning", "Ce que représente l'idée"),
                                   ("status", "Statut ou cadre envisagé"),
                                   ("attraction", "Ce qui attire"),
                                   ("access", "Conditions d'accès explorées")):
                    raw = st.text_area(label + " — choix multiples, une option par ligne",
                                       value="\n".join(updated["idea_questions"][key]),
                                       key=f"q_idea_options_{key}")
                    updated["idea_questions"][key] = _strings(raw)
                edited = st.form_submit_button("Enregistrer les corrections (brouillon)")
                if edited:
                    try:
                        save_questionnaire(ctx, case_id, updated, expected_row_version=view.row_version)
                        st.rerun()
                    except (ValueError, OrientationConflict, OrientationAccessDenied) as exc:
                        _err(exc)
            with st.expander("Aperçu en lecture seule du questionnaire côté bénéficiaire"):
                st.write(q["intro"])
                st.markdown("**Partie 1 — Mes idées**")
                if q["aps_ideas"]:
                    st.write("Idées antérieures à confirmer librement : " + ", ".join(q["aps_ideas"]))
                st.caption("Possibilité de déclarer ne pas avoir de piste ou d'en formuler une nouvelle.")
                for label, key in (("Sens de l'idée", "meaning"), ("Cadre professionnel envisagé", "status"),
                                   ("Ce qui attire", "attraction"), ("Conditions d'accès", "access")):
                    st.write(label + " : " + " / ".join(q["idea_questions"][key]))
                if q["enterprise_wording"]:
                    st.info("Perspective de l'entreprise, présentée séparément : " + q["enterprise_wording"])
                st.markdown("**Partie 2 — Mes repères personnels**")
                for section in q["sections"]:
                    st.write(section["question"])
                    st.caption("Réponses possibles : " + " / ".join(section["choices"]))
            st.warning("La publication rend ce questionnaire accessible au bénéficiaire et verrouille son contenu. Vérifiez l’aperçu complet avant de continuer.")
            publish_confirm = st.checkbox("J’ai relu les deux parties et je confirme la publication.")
            if st.button("Publier et verrouiller le questionnaire", type="primary", disabled=not publish_confirm):
                try:
                    lock_questionnaire(ctx, case_id, expected_row_version=view.row_version)
                    st.rerun()
                except (ValueError, OrientationConflict, OrientationAccessDenied) as exc:
                    _err(exc)
        return
        st.success(f"Questionnaire publié — version {view.questionnaire_version}. Son contenu est verrouillé.")
    st.markdown("### Contenu approuvé")
    with st.expander("Voir le questionnaire verrouillé", expanded=False):
        st.write(view.questionnaire["intro"])
        for section in view.questionnaire["sections"]:
            st.write(f"**{section['label']}** — {section['question']}")
            st.caption(", ".join(section["choices"]))
    if not view.invitation_open:
        st.caption("L'accès dans l'espace Bénéficiaire est distinct de l'envoi d'un e-mail. Le connecteur d'invitation/rappel doit être validé avec GDA.")
        if st.button("Mettre ce questionnaire à disposition du bénéficiaire", type="primary"):
            try:
                open_beneficiary_access(ctx, case_id, expected_row_version=view.row_version)
                st.rerun()
            except (ValueError, OrientationConflict, OrientationAccessDenied) as exc:
                _err(exc)
    else:
        st.info("Questionnaire disponible dans l'espace bénéficiaire via son lancement sécurisé. Aucun email n'a été envoyé par cette application.")
        if view.active_answers:
            st.success(f"Réponses envoyées définitivement — version {view.active_response_version}. Prêtes pour la relecture en séance.")
            if st.button("Ouvrir la relecture conjointe", type="primary"):
                _go("entry_joint_review")
        else:
            st.caption("En attente de la transmission finale du bénéficiaire.")


def _render_answer_form(answers: dict, q: dict, *, prefix: str) -> dict:
    """Editer les reponses, jamais le questionnaire. Aucune IA, meme masquee."""
    import streamlit as st
    result = copy.deepcopy(answers)
    st.markdown("### Partie 1 — Mes idées")
    st.caption("Les idées déjà mentionnées dans l'APS sont affichées sans être prévalidées. Vous pouvez les préciser, les retirer, en ajouter ou déclarer n'en avoir aucune. Chaque idée peut avoir son propre contexte.")
    result["no_idea_yet"] = st.checkbox("Je n'ai aucune idée de métier, d'activité ou de secteur pour le moment", value=answers["no_idea_yet"], key=f"{prefix}_noidea")
    if result["no_idea_yet"]:
        st.info("Aucune piste n'est exigée pour poursuivre le bilan. Les idées mentionnées dans l'APS ne sont pas considérées comme confirmées.")
    # Aucune idee APS n'est active par defaut : le beneficiaire la confirme
    # explicitement, sans avoir besoin de la retaper.
    current_ideas = [] if result["no_idea_yet"] else copy.deepcopy(result["ideas"])
    from_aps = set(q["aps_ideas"])
    kept_aps = st.multiselect("Parmi les idées mentionnées précédemment dans l'APS, lesquelles souhaitez-vous encore explorer ?",
                              options=q["aps_ideas"],
                              default=[x["wording"] for x in current_ideas if x["wording"] in from_aps],
                              key=f"{prefix}_aps_confirm", disabled=result["no_idea_yet"])
    ideas = [x for x in current_ideas if x["wording"] not in from_aps]
    for wording in kept_aps:
        previous = next((x for x in current_ideas if x["wording"] == wording), None)
        ideas.append(copy.deepcopy(previous) if previous else
                     {"wording": wording, "meaning": [], "status": [], "attraction": [], "access": [], "note": ""})
    # La saisie d'une nouvelle idee n'ajoute pas de question au Q fixe : elle
    # instancie une fiche selon les quatre rubriques fixes autorisees.
    raw_new = st.text_input("Nouvelle idée de métier, d'activité ou de secteur (facultatif)", key=f"{prefix}_newidea", max_chars=300,
                            disabled=result["no_idea_yet"])
    if raw_new.strip() and raw_new.strip().casefold() not in {x["wording"].casefold() for x in ideas}:
        ideas.append({"wording": raw_new.strip(), "meaning": [], "status": [], "attraction": [], "access": [], "note": ""})
    revised_ideas = []
    for i, idea in enumerate(ideas):
        with st.expander(f"Idée {i+1} — {idea['wording']}", expanded=True):
            item = copy.deepcopy(idea)
            item["wording"] = st.text_input("Métier, activité ou projet envisagé", value=idea["wording"], key=f"{prefix}_idea_{i}", max_chars=300)
            for field, title in (("meaning", "Ce que représente cette idée"),
                                 ("status", "Cadre ou statut envisagé"),
                                 ("attraction", "Ce qui m'attire"),
                                 ("access", "Conditions d'accès déjà vérifiées")):
                item[field] = st.multiselect(title, q["idea_questions"][field], default=idea[field], key=f"{prefix}_idea_{i}_{field}")
            item["note"] = st.text_area("Précisions éventuelles", value=idea["note"], key=f"{prefix}_idea_{i}_note", max_chars=1500)
            if st.checkbox("Conserver cette idée", value=True, key=f"{prefix}_idea_{i}_keep"):
                revised_ideas.append(item)
    result["ideas"] = revised_ideas
    if q["enterprise_wording"]:
        st.markdown("### Perspective évoquée par l'entreprise (distincte de mes idées)")
        st.write(q["enterprise_wording"])
        result["enterprise_position"] = st.selectbox("Ma position personnelle", ENTERPRISE_RESPONSES,
                                        index=list(ENTERPRISE_RESPONSES).index(answers["enterprise_position"]),
                                        key=f"{prefix}_enterprise")
        result["enterprise_note"] = st.text_area("Je précise si nécessaire", value=answers["enterprise_note"], key=f"{prefix}_enterprise_note")
    st.markdown("### Partie 2 — Mes repères personnels")
    st.caption("Ce sont vos choix actuels. Un score élevé ou bas dans un outil ne décide jamais pour vous.")
    for section in q["sections"]:
        code = section["code"]
        with st.expander(section["label"], expanded=True):
            st.write(section["question"])
            selected = st.multiselect(f"Sélectionner (maximum {section['max']})", section["choices"],
                                       default=answers["selections"].get(code, []), key=f"{prefix}_sec_{code}",
                                       max_selections=section["max"])
            result["selections"][code] = selected
            if section["required"] and not selected:
                choice = st.selectbox("Si aucun élément n'est retenu, préciser pourquoi", list(NONE_LABELS),
                           format_func=lambda x: NONE_LABELS[x],
                           index=list(NONE_LABELS).index(answers["none_reasons"].get(code, "")),
                           key=f"{prefix}_none_{code}")
                if choice:
                    result["none_reasons"][code] = choice
                else:
                    result["none_reasons"].pop(code, None)
            else:
                result["none_reasons"].pop(code, None)
            notes = st.text_area("Que signifie ce choix dans votre quotidien ? (facultatif)",
                                 value=answers["observations"].get(code, ""),
                                 max_chars=1200, key=f"{prefix}_note_{code}")
            result["observations"][code] = notes
    return result


def render_beneficiary_preparation(ctx, case_id: str) -> None:
    import streamlit as st
    view = read_preparation(ctx, case_id)
    st.title("Mes idées et mes repères avant la prochaine séance")
    if view.questionnaire is None:
        st.info("Votre accompagnateur prépare votre questionnaire. Aucune action requise pour le moment.")
        return
    q = view.questionnaire
    st.write(q["intro"])
    st.caption(f"Questionnaire publié — version {view.questionnaire_version}. Vos réponses ne sont ni interprétées ni complétées par une IA.")
    if view.active_answers is not None:
        st.success("Vos réponses ont été envoyées définitivement et conservées. Votre accompagnateur les reprendra avec vous en séance.")
        with st.expander("Relire mes réponses transmises"):
            st.json(view.active_answers, expanded=False)
        return
    if not ctx.has_scope("CP_BENEFICIARY_INTERACT"):
        st.warning("Vous pouvez consulter cette préparation, mais votre accès ne permet pas d'enregistrer les réponses. Demandez un lien de prescription adapté.")
        return
    data = view.responses or empty_answers(q)
    with st.form("go22_beneficiary_preparation"):
        answers = _render_answer_form(data, q, prefix=f"ben_{case_id}_Q{view.questionnaire_version}")
        save = st.form_submit_button("Enregistrer mon brouillon", type="primary")
        if save:
            try:
                save_beneficiary_answers(ctx, case_id, answers, expected_row_version=view.row_version)
                st.rerun()
            except (ValueError, OrientationConflict, OrientationAccessDenied) as exc:
                _err(exc)
    if view.responses is not None:
        st.markdown("### Transmission définitive")
        st.warning("Après transmission, ces réponses ne seront plus modifiables dans votre espace. Vous pourrez les revoir avec votre accompagnateur en entretien.")
        if st.button("Je confirme et transmets définitivement mes réponses", type="primary",
                     disabled=not ctx.has_scope("CP_BENEFICIARY_VALIDATE")):
            try:
                submit_beneficiary_answers(ctx, case_id, expected_row_version=view.row_version)
                st.rerun()
            except (ValueError, OrientationConflict, OrientationAccessDenied) as exc:
                _err(exc)
    st.caption("Aucun appel IA n'est exécuté ici. L'enregistrement est déterministe et soumis à validation serveur.")


def render_joint_review(ctx, case_id: str) -> None:
    import streamlit as st
    view = read_preparation(ctx, case_id)
    st.title("Relire les réponses avec le bénéficiaire")
    st.caption("Partage d'écran : le bénéficiaire reprend librement ses choix ; l'accompagnateur saisit les modifications en sa présence.")
    if view.active_answers is None:
        st.info("Le bénéficiaire n'a pas encore transmis ses réponses définitives. Cette étape reste en attente.")
        return
    st.info(f"Version des réponses à l’entrée : {view.active_response_version}. Les réponses initialement envoyées restent conservées.")
    if view.reviewed_in_session and view.joint_draft is None:
        st.success("Cette version a été confirmée conjointement en séance et sert de référence à la suite.")
    basis = view.joint_draft or view.active_answers
    with st.form("go22_joint_relecture"):
        revised = _render_answer_form(basis, view.questionnaire, prefix=f"joint_{case_id}_R{view.active_response_version}")
        if st.form_submit_button("Enregistrer les corrections en cours (non validées)"):
            try:
                save_joint_review(ctx, case_id, revised, expected_row_version=view.row_version)
                st.rerun()
            except (ValueError, OrientationConflict, OrientationAccessDenied) as exc:
                _err(exc)
    st.markdown("### Valider notre relecture")
    if view.joint_draft is not None:
        with st.expander("Voir les modifications proposées", expanded=True):
            from clarte360_cp.domain.preparation import difference
            st.json(difference(view.active_answers, view.joint_draft), expanded=True)
    confirmation = st.checkbox("Le bénéficiaire a relu les réponses affichées et confirme expressément les choix consignés en séance.", key=f"confirm_joint_{case_id}")
    method = st.radio("Modalité de confirmation recueillie", ["PARTAGE_ECRAN_ORAL", "EN_SEANCE_PRESENTIEL"],
                      format_func=lambda x: "Confirmation orale en partage d'écran" if x == "PARTAGE_ECRAN_ORAL" else "Confirmation orale en présence")
    st.caption("Il s'agit d'une confirmation fonctionnelle recueillie et tracée par l'accompagnateur, pas d'une signature électronique.")
    if st.button("Je valide professionnellement notre relecture", type="primary", disabled=not confirmation):
        try:
            confirm_joint_review(ctx, case_id, beneficiary_confirmed=True, method=method,
                                 expected_row_version=view.row_version)
            st.rerun()
        except (ValueError, OrientationConflict, OrientationAccessDenied) as exc:
            _err(exc)
    with st.expander("Historique des versions conservées"):
        for r in response_history(ctx, case_id):
            if r["state"] not in {"BENEFICIAIRE_VALIDE", "REVUE_CONJOINTE"}:
                continue
            state_label = "Envoyé par le bénéficiaire" if r["state"] == "BENEFICIAIRE_VALIDE" else "Relu ensemble"
            st.write(f"Version {r['no']} — {state_label} — {r['created_at']}")
    if st.button("Poursuivre vers la préparation des questions d’entretien"):
        _go("entry_directions")


def render_cav3_source_summary(ctx, case_id: str) -> None:
    import streamlit as st
    try:
        source = cav3_context(ctx, case_id)
    except (ValueError, OrientationAccessDenied):
        st.info("La préparation de questions d’entretien attend les réponses définitivement envoyées. Vous pouvez poursuivre l’exploration sans résultat IA.")
        return
    st.markdown("### Réponses de référence pour préparer les questions d’entretien")
    status_label = "Réponses relues en séance" if source["status"] == "REVU_EN_SEANCE" else "Réponses envoyées, à relire en séance"
    st.caption(f"Réponses version {source['response_version']} · {status_label}. Les brouillons et le CV n’entrent pas dans cette préparation.")
    if source["status"] == "PREPARATOIRE_NON_VALIDE":
        st.warning("Préparation possible pour l'accompagnateur, mais le contenu doit encore être revu avec le bénéficiaire en séance.")
    answers = source["reponses"]
    if answers["ideas"]:
        st.write("**Idées exprimées :** " + ", ".join(x["wording"] for x in answers["ideas"]))
    elif answers["no_idea_yet"]:
        st.write("**Aucune idée formulée à ce stade** : ne pas inventer une piste.")
    for code, chosen in answers["selections"].items():
        if chosen:
            st.write(f"**{code.replace('_',' ').title()} :** " + ", ".join(chosen))
    st.caption("Une éventuelle proposition d’entretien restera une aide à relire avec le bénéficiaire, jamais une décision automatique.")


# RC3 - Dispatch versionné. Les dossiers RC2 conservent leurs anciens écrans
# et formats, les nouveaux dossiers utilisent le questionnaire unique V2.
_render_builder_rc2 = render_questionnaire_builder
_render_beneficiary_rc2 = render_beneficiary_preparation
_render_joint_rc2 = render_joint_review
_render_cav3_rc2 = render_cav3_source_summary


def render_questionnaire_builder(ctx, case_id: str) -> None:
    from clarte360_cp.domain.preparation_v2 import SCHEMA_Q_V2
    from clarte360_cp.ui.preparation_rc3 import render_builder
    view = read_preparation(ctx, case_id)
    if view.questionnaire is not None and view.questionnaire.get("schema") != SCHEMA_Q_V2:
        return _render_builder_rc2(ctx, case_id)
    return render_builder(ctx, case_id)


def render_beneficiary_preparation(ctx, case_id: str) -> None:
    from clarte360_cp.domain.preparation_v2 import SCHEMA_Q_V2
    from clarte360_cp.ui.preparation_rc3 import render_beneficiary
    view = read_preparation(ctx, case_id)
    if view.questionnaire is not None and view.questionnaire.get("schema") != SCHEMA_Q_V2:
        return _render_beneficiary_rc2(ctx, case_id)
    return render_beneficiary(ctx, case_id)


def render_joint_review(ctx, case_id: str) -> None:
    from clarte360_cp.domain.preparation_v2 import SCHEMA_Q_V2
    from clarte360_cp.ui.preparation_rc3 import render_review
    view = read_preparation(ctx, case_id)
    if view.questionnaire is not None and view.questionnaire.get("schema") != SCHEMA_Q_V2:
        return _render_joint_rc2(ctx, case_id)
    return render_review(ctx, case_id)


def render_cav3_source_summary(ctx, case_id: str) -> None:
    from clarte360_cp.domain.preparation_v2 import SCHEMA_Q_V2
    from clarte360_cp.ui.preparation_rc3 import render_cav3
    view = read_preparation(ctx, case_id)
    if view.questionnaire is not None and view.questionnaire.get("schema") != SCHEMA_Q_V2:
        return _render_cav3_rc2(ctx, case_id)
    return render_cav3(ctx, case_id)
