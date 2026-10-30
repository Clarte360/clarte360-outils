"""GO22 - Trois écrans métier accompagnés AVANT le travail détaillé sur le CV."""
from __future__ import annotations

from clarte360_cp.application.orientation import (
    OrientationAccessDenied, OrientationConflict, feedback_orientation,
    publish_orientation, read_orientation, save_orientation,
)
from clarte360_cp.domain.orientation import (
    DECISIONS, DIRECTION_ORIGINS, ENTERPRISE_CHOICES, IDEA_ORIGINS,
    MOTORS, PREFERENCES, RIASEC, TOOLS,
    clone_orientation, new_direction, new_idea,
)
from clarte360_cp.framework.navigation import set_page

DECISION_LABELS = {
    "A_DECIDER": "À décider ensemble",
    "A_EXPLORER": "Oui, je veux explorer",
    "A_REFORMULER": "Je souhaite reformuler",
    "PLUS_AUJOURDHUI": "Plus aujourd'hui",
    "JE_NE_SAIS_PAS": "Je ne sais pas encore",
}
ENTERPRISE_LABELS = {
    "A_DECIDER": "Choix non encore exprimé",
    "NON_CONCERNE": "Sans objet",
    "A_CLARIFIER": "J'aimerais mieux comprendre",
    "SOUHAITE_EXPLORER": "Je souhaite l'explorer",
    "NE_SOUHAITE_PAS": "Je ne souhaite pas l'explorer",
    "JE_NE_SAIS_PAS": "Je ne sais pas encore",
}


def _open(page: str) -> None:
    import streamlit as st
    set_page(st.session_state, page)
    st.rerun()


def _store(ctx, case_id: str, view, content: dict) -> None:
    import streamlit as st
    try:
        save_orientation(ctx, case_id, content, expected_row_version=view.current_version)
    except (OrientationConflict, OrientationAccessDenied, ValueError) as exc:
        st.error(str(exc))
        return
    st.rerun()


def _form_intro(stage: int, title: str, info: str) -> None:
    import streamlit as st
    st.title(title)
    st.caption(f"Mes repères et mes premières directions — étape {stage}/3. {info}")
    st.info("Ce travail est conduit en séance avec le bénéficiaire. Les résultats de tests éclairent une réflexion ; ils ne décident pas d'un métier.")


def render_ideas(ctx, case_id: str) -> None:
    import streamlit as st
    view = read_orientation(ctx, case_id)
    doc = view.current
    _form_intro(1, "Mes idées à moi", "D'abord les envies et les idées personnelles, sans filtrage.")
    st.markdown("### Ce que j'envisage personnellement")
    st.caption("Une idée peut être un métier précis, un secteur, une activité ou une envie encore imprécise. Même une idée très éloignée des résultats des questionnaires reste légitime.")
    with st.form("go22_add_idea", clear_on_submit=True):
        wording = st.text_input("J'aimerais explorer…", max_chars=500, placeholder="Par exemple : travailler avec des enfants")
        origin = st.selectbox("D'où vient cette idée ?", options=list(IDEA_ORIGINS), format_func=lambda x: IDEA_ORIGINS[x])
        add = st.form_submit_button("Ajouter cette idée", type="primary")
        if add:
            try:
                clone = clone_orientation(doc)
                clone["ideas"].append(new_idea(wording, origin))
                clone["no_idea_yet"] = False
                _store(ctx, case_id, view, clone)
            except ValueError as exc:
                st.error(str(exc))
    if not doc["ideas"]:
        st.caption("Aucune idée exprimée pour le moment.")
    else:
        for idea in doc["ideas"]:
            with st.container(border=True):
                st.markdown(f"**{idea['current']}**")
                st.caption(f"Origine : {IDEA_ORIGINS.get(idea['origin'], 'À préciser')} · Mots initiaux conservés : « {idea['original']} »")
                options = list(DECISIONS)
                choice = st.selectbox("Quelle est la position actuelle ?", options,
                                     index=options.index(idea["decision"]), format_func=lambda x: DECISION_LABELS[x],
                                     key=f"ideachoice_{idea['id']}")
                with st.expander("Reformuler avec les mots du bénéficiaire", expanded=False):
                    new_wording = st.text_input("Nouvelle formulation", value=idea["current"],
                                                key=f"ideawording_{idea['id']}", max_chars=500)
                if st.button("Enregistrer cette position", key=f"updateidea_{idea['id']}"):
                    clone = clone_orientation(doc)
                    for item in clone["ideas"]:
                        if item["id"] == idea["id"]:
                            item["decision"] = choice
                            item["current"] = new_wording
                    _store(ctx, case_id, view, clone)
    if not doc["ideas"]:
        if st.button("Je ne sais pas encore vers quoi aller", key="go22_noidea"):
            clone = clone_orientation(doc)
            clone["no_idea_yet"] = True
            _store(ctx, case_id, view, clone)
    if doc["no_idea_yet"]:
        st.success("La personne n'a pas encore identifié de direction. C'est une réponse parfaitement recevable.")

    st.markdown("### Perspectives éventuellement évoquées par mon entreprise")
    st.caption("Le point de vue de l'entreprise est distinct des idées personnelles. Son financement n'en fait pas un projet obligatoire. Ce bloc ne donne aucun accès à l'employeur.")
    employer = doc["enterprise"]
    with st.form("go22_enterprise"):
        present = st.checkbox("Une perspective professionnelle a été communiquée par l'entreprise", value=employer["present"])
        text = st.text_area("Perspective formulée par l'entreprise", value=employer["wording"],
                            max_chars=1000, placeholder="Poste, mobilité, évolution possible…")
        source = st.text_input("Origine explicite (ex. volet entreprise APS, date)", value=employer["source_label"], max_chars=200)
        choice = st.selectbox("Ce que le bénéficiaire souhaite en faire", list(ENTERPRISE_CHOICES)[1:] if present else ["NON_CONCERNE"],
                              index=(list(ENTERPRISE_CHOICES)[1:].index(employer["choice"]) if present and employer["choice"] in list(ENTERPRISE_CHOICES)[1:] else 0),
                              format_func=lambda x: ENTERPRISE_LABELS[x])
        if st.form_submit_button("Enregistrer le contexte entreprise"):
            clone = clone_orientation(doc)
            clone["enterprise"] = {"present": present, "wording": text if present else "",
                                    "source_label": source if present else "",
                                    "choice": choice if present else "NON_CONCERNE"}
            _store(ctx, case_id, view, clone)
    if view.has_draft:
        st.caption("Les modifications sont enregistrées côté serveur, mais non visibles dans l'espace Bénéficiaire tant qu'elles ne sont pas publiées.")
    if st.button("Continuer vers mes repères", type="primary"):
        _open("entry_reperes")


def _parse_terms(raw: str) -> list[str]:
    return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]


def render_reperes(ctx, case_id: str, sources_present: dict[str, bool]) -> None:
    import streamlit as st
    view = read_orientation(ctx, case_id)
    doc = view.current
    _form_intro(2, "Mes repères professionnels", "Relire les cinq éclairages déjà travaillés, sans attribuer de résultat inventé.")
    for code, short, description in TOOLS:
        entry = doc["reviews"][code]
        with st.expander(f"{short} — {description}", expanded=code == "BOUSSOLE_VALEURS"):
            if sources_present.get(code):
                st.success("Source signalée comme présente dans le dossier. Les résultats exacts restent à relire avec le bénéficiaire.")
            else:
                st.warning("Rapport non introduit dans C&P. Ne pas présenter une saisie manuelle comme un résultat automatiquement extrait du test.")
            with st.form(f"go22_tool_{code}"):
                source_note = st.text_area("Ce que dit le résultat déjà connu / le compte rendu de séance", value=entry["source_note"], max_chars=2000,
                                           help="Saisie accompagnateur vérifiée avec le bénéficiaire. Ne pas inventer de score ou de facette.")
                if code == "BOUSSOLE_VALEURS":
                    val = st.text_input("Mes trois valeurs choisies pour la suite (séparer par des virgules)",
                                        value=", ".join(entry["retained"]), max_chars=500)
                    st.caption("Ce sont les valeurs désignées par le bénéficiaire, pas les trois notes les plus élevées.")
                    retained = _parse_terms(val)
                    avoided = []
                elif code == "MOTEURS_PRO":
                    retained = st.multiselect("Les moteurs que je souhaite retrouver", options=list(MOTORS), default=entry["retained"])
                    avoided = []
                elif code == "PREFERENCES_PRO":
                    retained = st.multiselect("Conditions de travail à rechercher", options=list(PREFERENCES), default=entry["retained"])
                    avoided = st.multiselect("Conditions que je souhaite plutôt éviter", options=list(PREFERENCES), default=entry["avoided"])
                elif code == "IPIP_REPORT":
                    val = st.text_area("Éléments de fonctionnement que je reconnais ou nuance (un élément par ligne)",
                                       value="\n".join(entry["retained"]), max_chars=2000)
                    retained = [v.strip() for v in val.splitlines() if v.strip()]
                    avoided = []
                    st.caption("Conditions de réussite / vigilance uniquement. Aucun diagnostic, aucune affectation métier automatique.")
                else:
                    retained = st.multiselect("Familles d'activités qui m'attirent", options=list(RIASEC), default=entry["retained"])
                    avoided = st.multiselect("Familles qui m'intéressent moins (optionnel)", options=list(RIASEC), default=entry["avoided"])
                    st.caption("Intérêt pour une activité ≠ compétence démontrée.")
                reflection = st.text_area("Ce qui me surprend, ce que je nuance ou ce que je veux retenir", value=entry["reflection"], max_chars=1200)
                if st.form_submit_button(f"Enregistrer ma relecture — {short}"):
                    clone = clone_orientation(doc)
                    clone["reviews"][code] = {"source_note": source_note,
                                               "retained": retained, "avoided": avoided,
                                               "reflection": reflection}
                    _store(ctx, case_id, view, clone)
    with st.form("go22_reperes_newidea", clear_on_submit=True):
        st.markdown("#### Cela me fait penser à une autre idée…")
        new_text = st.text_input("Une autre idée qui apparaît en relisant mes repères", max_chars=500)
        if st.form_submit_button("Ajouter cette idée à mes idées personnelles"):
            try:
                clone = clone_orientation(doc)
                clone["ideas"].append(new_idea(new_text, "APRES_RELECTURE"))
                clone["no_idea_yet"] = False
                _store(ctx, case_id, view, clone)
            except ValueError as exc:
                st.error(str(exc))
    if st.button("Continuer vers mes premières directions", type="primary"):
        _open("entry_directions")


def render_directions(ctx, case_id: str) -> None:
    import streamlit as st
    view = read_orientation(ctx, case_id)
    doc = view.current
    _form_intro(3, "Mes premières directions à explorer", "Des hypothèses choisies et toujours révisables, pas une décision définitive de métier.")
    st.markdown("#### Les idées que la personne souhaite explorer")
    ideas = [x for x in doc["ideas"] if x["decision"] == "A_EXPLORER"]
    for idea in ideas:
        st.write(f"• {idea['current']} — {IDEA_ORIGINS[idea['origin']]}")
    if not ideas:
        st.caption("Aucune direction spontanée confirmée pour le moment. Le bilan peut faire émerger des possibilités progressivement.")
    if doc["enterprise"]["present"]:
        st.caption(f"Perspective de l'entreprise (distincte) : {doc['enterprise']['wording']} — {ENTERPRISE_LABELS[doc['enterprise']['choice']]}")
    st.markdown("### Directions formulées ensemble")
    st.caption("On ne limite pas les idées initiales à trois. Le choix d'un à trois métiers ROME se fera ultérieurement, après le parcours et les compétences.")
    for direction in doc["directions"]:
        with st.container(border=True):
            st.write(f"**{direction['wording']}**")
            if direction["reason"]:
                st.caption(f"Pourquoi explorer : {direction['reason']}")
            status = st.selectbox("Position actuelle du bénéficiaire", list(DECISIONS),
                                  index=list(DECISIONS).index(direction["decision"]),
                                  format_func=lambda x: DECISION_LABELS[x], key=f"dir_{direction['id']}")
            if st.button("Enregistrer", key=f"dirsave_{direction['id']}"):
                clone = clone_orientation(doc)
                for d in clone["directions"]:
                    if d["id"] == direction["id"]:
                        d["decision"] = status
                _store(ctx, case_id, view, clone)
    with st.form("go22_add_direction", clear_on_submit=True):
        idea_labels = [i["current"] for i in ideas]
        defaults = ["Nouvelle direction formulée ensemble", *idea_labels]
        suggested = st.selectbox("Point de départ (optionnel)", defaults)
        title = st.text_input("Direction à explorer, avec les mots du bénéficiaire", max_chars=500)
        why = st.text_area("Pourquoi cette direction mérite d'être explorée (sans preuve supposée)", max_chars=1000)
        if st.form_submit_button("Ajouter la direction"):
            try:
                wording = title.strip() or (suggested if suggested != defaults[0] else "")
                clone = clone_orientation(doc)
                clone["directions"].append(new_direction(wording, why))
                _store(ctx, case_id, view, clone)
            except ValueError as exc:
                st.error(str(exc))
    st.markdown("### Partage avec le bénéficiaire")
    st.caption("La publication présente seulement une version revue en séance ; aucune information n'est transmise à l'entreprise. La confirmation du bénéficiaire est distincte de celle de l'accompagnateur.")
    if view.published_version is not None:
        if view.feedback == "CONFIRME":
            st.success("Le bénéficiaire a confirmé la version actuellement publiée.")
        elif view.feedback == "CORRECTION_DEMANDEE":
            st.warning(f"Correction demandée : {view.feedback_comment or 'À préciser'}")
        else:
            st.info("Un résultat est publié, en attente de retour du bénéficiaire.")
    if st.button("Publier ce résultat pour relecture", type="primary", disabled=not view.has_draft or not ctx.has_scope("CP_PUBLISH")):
        try:
            publish_orientation(ctx, case_id, expected_row_version=view.current_version)
        except (OrientationConflict, OrientationAccessDenied, ValueError) as exc:
            st.error(str(exc))
        else:
            st.success("Nouvelle version publiée dans l'espace bénéficiaire.")
            st.rerun()
    if st.button("Poursuivre vers l'analyse du parcours / CV"):
        _open("entry_sources")


def render_beneficiary_orientation(ctx, case_id: str) -> None:
    import streamlit as st
    view = read_orientation(ctx, case_id)
    st.title("Mes repères et mes premières directions")
    st.caption("La version visible ici est celle que votre accompagnateur a publiée à votre intention. Elle ne sera pas communiquée à votre employeur.")
    if view.published is None:
        st.info("Votre accompagnateur prépare cette étape. Aucun document de travail interne n'est encore publié.")
        if st.button("Revenir à mon parcours"):
            _open("b_journey")
        return
    doc = view.published
    st.markdown("### Mes idées à moi")
    if doc["ideas"]:
        for idea in doc["ideas"]:
            st.write(f"• {idea['current']} — {DECISION_LABELS[idea['decision']]}")
    elif doc["no_idea_yet"]:
        st.write("Je n'ai pas encore trouvé de direction précise.")
    if doc["enterprise"]["present"]:
        st.markdown("### Une perspective évoquée par mon entreprise")
        st.write(doc["enterprise"]["wording"])
        st.caption(f"Ma position : {ENTERPRISE_LABELS[doc['enterprise']['choice']]}. Cette idée ne m'est pas imposée.")
    st.markdown("### Ce que je souhaite retrouver dans mon futur travail")
    for code, short, _description in TOOLS:
        tool = doc["reviews"][code]
        if not tool["retained"] and not tool["reflection"] and not tool["avoided"]:
            continue
        with st.expander(short, expanded=code == "BOUSSOLE_VALEURS"):
            if tool["retained"]:
                st.write("À retenir : " + ", ".join(tool["retained"]))
            if tool["avoided"]:
                st.write("Plutôt à éviter : " + ", ".join(tool["avoided"]))
            if tool["reflection"]:
                st.write(tool["reflection"])
    st.markdown("### Mes directions actuelles")
    directions = [d for d in doc["directions"] if d["decision"] == "A_EXPLORER"]
    if directions:
        for d in directions:
            st.write(f"• {d['wording']}")
    else:
        st.info("Aucune direction spécifique n'a encore été retenue. Ce n'est pas une mauvaise réponse.")
    st.markdown("### Ma relecture")
    if view.feedback == "CONFIRME":
        st.success("Vous avez confirmé cette version.")
    elif view.feedback == "CORRECTION_DEMANDEE":
        st.warning("Vous avez demandé une correction. Votre accompagnateur pourra préparer une nouvelle version.")
        if view.feedback_comment:
            st.write(view.feedback_comment)
    elif not ctx.has_scope("CP_BENEFICIARY_VALIDATE"):
        st.info("La consultation est possible ; la confirmation nécessite un droit de validation actif dans le lancement sécurisé.")
    else:
        st.warning("Une seule réponse est possible pour cette version. Une fois votre confirmation ou votre demande envoyée, contactez votre accompagnateur pour toute correction complémentaire.")
        confirm_key = f"orientation_feedback_confirm_{case_id}_{view.published_version}"
        confirm_send = st.checkbox("J’ai relu cette version et confirme l’envoi de ma réponse.", key=confirm_key)
        if st.button("Confirmer cette version", type="primary", disabled=not confirm_send):
            try:
                feedback_orientation(ctx, case_id, published_version=view.published_version, decision="CONFIRME")
                st.rerun()
            except (OrientationConflict, OrientationAccessDenied, ValueError) as exc:
                st.error(str(exc))
        with st.form("go22_ben_correction"):
            note = st.text_area("Je souhaite préciser ou corriger…", max_chars=1000)
            confirm_correction = st.checkbox("J’ai relu ma demande et confirme son envoi.")
            if st.form_submit_button("Envoyer ma demande de correction", disabled=not confirm_correction):
                try:
                    feedback_orientation(ctx, case_id, published_version=view.published_version,
                                         decision="CORRECTION_DEMANDEE", comment=note)
                    st.rerun()
                except (OrientationConflict, OrientationAccessDenied, ValueError) as exc:
                    st.error(str(exc))
    if st.button("Retour à mon parcours"):
        _open("b_journey")
