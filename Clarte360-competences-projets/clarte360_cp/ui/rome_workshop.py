"""Sélection métier ROME et atelier de rapprochement Accompagnateur/Bénéficiaire."""
from __future__ import annotations

import hashlib
from html import escape
import re

from clarte360_cp.application.rome_catalog import (
    RomeCatalogError, decide_rome_target, prepare_local_rome_target, read_local_rome_metadata,
    prepare_rome_target, read_rome_targets, search_local_rome, search_rome_metiers,
)
from clarte360_cp.application.rome_matching import (
    RomeMatchingError, add_session_experience, read_career_cards, read_rome_matching_workspace,
    run_rome_matching_analysis, save_rome_matching_review, update_session_experience,
)
from clarte360_cp.application.rome_interest_context import rome_interest_context
from clarte360_cp.application.intersession import (
    TASK_TYPES, close_intersession_task, create_intersession_task, read_intersession_tasks,
)
from clarte360_cp.application.orientation import OrientationConflict
from clarte360_cp.connectors.cav3_ai import ai_ready
from clarte360_cp.domain.rome_matching import EXERCISE_LEVELS, MATCH_STATUSES


_CATEGORY_LABELS = {
    "SAVOIR": "Savoirs — ce que je connais",
    "SAVOIR_FAIRE": "Savoir-faire — ce que je sais faire",
    "SAVOIR_ETRE": "Savoir-être professionnels — ma façon d’agir au travail",
}


def render_career_enrichment(ctx, case_id: str) -> None:
    """Guided, human-reviewed career cards; source documents stay in GDA."""
    import streamlit as st
    st.markdown("#### Construire les cartes du parcours avec le bénéficiaire")
    st.info("L’accompagnateur et le bénéficiaire complètent ensemble les faits utiles : activités, autonomie, résultats, outils et savoirs. Les éléments d’études sans diplôme et d’apprentissage personnel sont recevables. Le document source reste dans l’espace commun GDA ; une proposition issue du CV relié manuellement à sa référence reste à confirmer et doit être relue en séance.")
    try:
        cards = read_career_cards(ctx, case_id)
    except Exception:
        st.error("Les cartes du parcours ne peuvent pas être lues pour cette session accompagnateur.")
        return
    kinds = ["EMPLOI", "ETUDE", "FORMATION", "AUTOFORMATION", "AUTRE"]
    kind_labels = {"EMPLOI": "Expérience professionnelle", "ETUDE": "Études (avec ou sans diplôme)",
        "FORMATION": "Formation", "AUTOFORMATION": "Apprentissage personnel / autodidacte", "AUTRE": "Autre élément de parcours"}
    level_labels = {None: "À préciser avec le bénéficiaire", 1: "1 — Pratique encadrée / contribution",
        2: "2 — Maîtrise autonome", 3: "3 — Pilotage, expertise ou transmission"}
    for card in cards:
        detail = card["details"]
        with st.expander(f"{kind_labels.get(card['kind'], card['kind'])} — {card['title']}", expanded=False):
            if card["source_linked"]:
                st.caption("Cette carte conserve une référence de source ; le fichier original n’est pas dupliqué dans C&P.")
            else:
                st.caption("Apport structuré en C&P. Associez le document source depuis l’espace commun lorsqu’un document est utilisé.")
            with st.form(f"career_card_form_{card['id']}"):
                kind = st.selectbox("Nature", kinds, index=kinds.index(card["kind"]) if card["kind"] in kinds else kinds.index("AUTRE"),
                    format_func=lambda value: kind_labels[value], key=f"career_kind_{card['id']}")
                title = st.text_input("Intitulé", value=card["title"], max_chars=240, key=f"career_title_{card['id']}")
                org = st.text_input("Structure / organisme (facultatif)", value=card["organization"], max_chars=240, key=f"career_org_{card['id']}")
                dates = st.columns(2)
                start = dates[0].text_input("Début (facultatif)", value=card["period_start"], max_chars=20, key=f"career_start_{card['id']}")
                end = dates[1].text_input("Fin (facultatif)", value=card["period_end"], max_chars=20, key=f"career_end_{card['id']}")
                context_text = st.text_area("Contexte / secteur", value=str(detail.get("context", "")), max_chars=2400, key=f"career_context_{card['id']}")
                activities = st.text_area("Activités, contenus étudiés ou missions", value=str(detail.get("activities", "")), max_chars=2400, key=f"career_activities_{card['id']}")
                autonomy = st.text_area("Responsabilités et autonomie", value=str(detail.get("autonomie", "")), max_chars=1200, key=f"career_autonomy_{card['id']}")
                achievements = st.text_area("Réalisations ou résultats", value=str(detail.get("realisations", "")), max_chars=2400, key=f"career_results_{card['id']}")
                tools_text = st.text_area("Outils, méthodes ou référentiels", value=str(detail.get("outils", "")), max_chars=1200, key=f"career_tools_{card['id']}")
                knowledge = st.text_area("Savoirs et savoir-faire mobilisés", value=str(detail.get("savoirs", "")), max_chars=1600, key=f"career_knowledge_{card['id']}")
                level = detail.get("niveau_exercice")
                if level not in {None, 1, 2, 3}:
                    level = None
                level_label = st.selectbox("Niveau d’exercice discuté pour cette expérience", list(level_labels.values()),
                    index=list(level_labels).index(level), help="À choisir à partir de faits concrets, jamais du seul titre du poste.", key=f"career_level_{card['id']}")
                beneficiary_reviewed = st.checkbox("Le bénéficiaire a relu cette carte avec moi", value=detail.get("statut_humain") == "RELUE_EN_SEANCE", key=f"career_reviewed_{card['id']}")
                saved = st.form_submit_button("Enregistrer la carte", type="primary", use_container_width=True)
            if saved:
                try:
                    update_session_experience(ctx, case_id, card["id"], title=title, kind=kind,
                        organization=org, period_start=start, period_end=end, context=context_text,
                        activities=activities, autonomy=autonomy, achievements=achievements,
                        tools=tools_text, knowledge=knowledge, level_of_exercise=list(level_labels)[list(level_labels.values()).index(level_label)],
                        beneficiary_reviewed=beneficiary_reviewed)
                    st.success("Carte enregistrée. Les rapprochements ROME antérieurs devront être revus si les faits ont changé.")
                    st.rerun()
                except (ValueError, RomeMatchingError) as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("La carte n’a pas pu être enregistrée.")
    with st.expander("Ajouter un apport de parcours discuté en séance", expanded=not bool(cards)):
        st.caption("Cette saisie décrit un fait de parcours quand la source partagée n’est pas encore reliée. Elle reste identifiée comme apport de séance, à confirmer, et ne crée aucun fichier.")
        with st.form(f"career_card_add_{case_id}"):
            kind = st.selectbox("Nature de l’élément", kinds,
                format_func=lambda value: kind_labels[value], key=f"career_add_kind_{case_id}")
            title = st.text_input("Intitulé de l’expérience, des études ou de la formation", max_chars=240,
                key=f"career_add_title_{case_id}")
            org = st.text_input("Structure / organisme (facultatif)", max_chars=240,
                key=f"career_add_org_{case_id}")
            dates = st.columns(2)
            start = dates[0].text_input("Début (facultatif)", max_chars=20, key=f"career_add_start_{case_id}")
            end = dates[1].text_input("Fin (facultatif)", max_chars=20, key=f"career_add_end_{case_id}")
            context_text = st.text_area("Contexte / secteur", max_chars=2400, key=f"career_add_context_{case_id}")
            activities = st.text_area("Activités, contenus étudiés ou missions", max_chars=2400, key=f"career_add_activities_{case_id}")
            autonomy = st.text_area("Responsabilités et autonomie", max_chars=1200, key=f"career_add_autonomy_{case_id}")
            achievements = st.text_area("Réalisations ou résultats", max_chars=2400, key=f"career_add_results_{case_id}")
            tools_text = st.text_area("Outils, méthodes ou référentiels", max_chars=1200, key=f"career_add_tools_{case_id}")
            knowledge = st.text_area("Savoirs et savoir-faire mobilisés", max_chars=1600, key=f"career_add_knowledge_{case_id}")
            level_label = st.selectbox("Niveau d’exercice discuté", list(level_labels.values()),
                help="À préciser à partir des faits pour cette expérience. Le titre du poste ne suffit pas.",
                key=f"career_add_level_{case_id}")
            added = st.form_submit_button("Ajouter au parcours", type="primary", use_container_width=True)
        if added:
            try:
                add_session_experience(ctx, case_id, title=title, kind=kind, organization=org,
                    period_start=start, period_end=end, context=context_text, activities=activities,
                    autonomy=autonomy, achievements=achievements, tools=tools_text, knowledge=knowledge,
                    level_of_exercise=list(level_labels)[list(level_labels.values()).index(level_label)])
                st.success("Apport de séance ajouté, à confirmer avec le bénéficiaire.")
                st.rerun()
            except (ValueError, RomeMatchingError) as exc:
                st.error(str(exc))
            except Exception:
                st.error("L’apport n’a pas pu être ajouté au parcours.")
    if not cards:
        st.info("Aucune carte de parcours n’est encore enregistrée.")
    else:
        st.caption(f"{len(cards)} carte(s) de parcours enregistrée(s). Toute modification invalide les rapprochements ROME à revoir.")


def render_rome_target_selection(ctx, case_id: str) -> None:
    import streamlit as st
    st.markdown("#### 1 — Choisir les métiers à étudier avec le bénéficiaire")
    st.markdown("Recherchez les métiers dans l’application, puis examinez et validez ensemble de 1 à 3 choix. Le bénéficiaire n’a pas de recherche ROME externe à faire.")
    metadata = read_local_rome_metadata()
    entry_count = f"{metadata['entry_count']:,}".replace(",", "\u00a0")
    st.caption(f"La recherche interroge d’abord l’API officielle ROME Métiers. Si elle est indisponible ou sans résultat, l’application utilise le snapshot local daté {metadata['version']} ({entry_count} codes, publié le {metadata['publication_date']}).")
    search_query_key = f"rome_search_query_{case_id}"
    search_results_key = f"rome_search_results_{case_id}"
    search_source_key = f"rome_search_source_{case_id}"
    search_issue_key = f"rome_search_issue_{case_id}"
    with st.form(key=f"rome_search_form_{case_id}"):
        query_input = st.text_input("Rechercher un code, un métier ou une appellation", max_chars=120,
                                    placeholder="Ex. M1203, comptable, assistant paie", key=f"rome_search_input_{case_id}")
        search_submitted = st.form_submit_button("Rechercher dans le ROME", type="primary", use_container_width=True)
    if search_submitted:
        submitted_query = query_input.strip()
        st.session_state[search_query_key] = submitted_query
        results = ()
        source = ""
        issue = ""
        if submitted_query:
            try:
                results = search_rome_metiers(submitted_query, limit=60)
                source = "API France Travail · ROME Métiers"
            except RomeCatalogError as exc:
                issue = str(exc)
            if not results:
                try:
                    results = search_local_rome(submitted_query, limit=60)
                    source = f"Référentiel local daté {metadata['version']}"
                    if not issue:
                        issue = "L’API n’a renvoyé aucun résultat pour cette recherche."
                except RomeCatalogError as exc:
                    issue = issue or str(exc)
        st.session_state[search_results_key] = results
        st.session_state[search_source_key] = source
        st.session_state[search_issue_key] = issue
    query = st.session_state.get(search_query_key, "")
    matches = st.session_state.get(search_results_key, ())
    match_source = st.session_state.get(search_source_key, "")
    search_issue = st.session_state.get(search_issue_key, "")
    direct_code = st.text_input("Code ROME direct (interrogation France Travail)", max_chars=5,
                                placeholder="Ex. M1203", key="rome_api_direct_code").strip().upper()
    if direct_code and re.fullmatch(r"[A-Z]\d{4}", direct_code):
        if st.button("Charger ce code depuis l’API France Travail", type="primary",
                     key="rome_api_direct_fetch", use_container_width=True):
            try:
                created = prepare_rome_target(ctx, case_id, direct_code, force_refresh=True)
                st.success(f"Fiche API chargée : {created['code']} — {created['label']}. Examinez-la avec le bénéficiaire avant de retenir le métier.")
                st.rerun()
            except RomeCatalogError as exc:
                st.error(f"La fiche API n’a pas pu être chargée : {exc}")
    elif direct_code:
        st.caption("Le code doit contenir une lettre suivie de quatre chiffres.")
    if not query.strip():
        st.caption("Saisissez quelques lettres ou le code ROME, puis lancez la recherche pour afficher les correspondances.")
    elif matches:
        st.caption(f"Résultats : {match_source}")
        if search_issue:
            st.caption(f"Recherche locale de secours : {search_issue}")
        local_options = {f"{row['code']} — {row['label']}" + (f" · appellation : {row['appellation']}" if row.get("appellation") else ""): row['code'] for row in matches}
        selected_local = st.selectbox("Métiers ROME correspondants", list(local_options), key="rome_local_result")
        selected_code = local_options[selected_local]
        api_col, local_col = st.columns(2)
        if api_col.button("Charger la fiche à jour depuis l’API", type="primary", key="rome_api_selected_fetch", use_container_width=True):
            try:
                created = prepare_rome_target(ctx, case_id, selected_code, force_refresh=True)
                st.success(f"Fiche API chargée : {created['code']} — {created['label']}. Examinez-la avec le bénéficiaire avant de retenir le métier.")
                st.rerun()
            except RomeCatalogError as exc:
                st.error(f"La fiche API n’a pas pu être chargée : {exc} La fiche locale datée reste disponible ci-dessous.")
        if local_col.button("Utiliser la fiche locale datée", key="rome_local_fetch", use_container_width=True):
            try:
                created = prepare_local_rome_target(ctx, case_id, selected_code)
                st.success(f"Fiche locale chargée : {created['code']} — {created['label']}. Examinez-la avec le bénéficiaire avant de retenir le métier.")
                st.rerun()
            except RomeCatalogError as exc:
                st.error(str(exc))
            except Exception:
                st.error("La fiche locale n’a pas pu être enregistrée dans ce dossier.")
    elif query.strip():
        if search_issue:
            st.warning(f"Recherche API indisponible : {search_issue}")
        st.info("Aucun résultat ROME pour cette recherche. Essayez une appellation plus courte ou le code ROME.")
    try:
        targets = read_rome_targets(ctx, case_id)
    except Exception:
        st.error("Les métiers du dossier ne peuvent pas être lus dans cette session.")
        return
    active = [x for x in targets if x["status"] == "ACTIVE"]
    proposals = [x for x in targets if x["status"] == "PROPOSITION"]
    if active:
        st.markdown("##### Métiers retenus pour l’étude")
        cols = st.columns(min(3, len(active)))
        for index, target in enumerate(active):
            with cols[index % len(cols)]:
                origin = "Référentiel ROME local" if target.get("source_provider") == "FRANCE_TRAVAIL_OPENDATA" else "API France Travail"
                version = f" · {target['source_version']}" if target.get("source_version") else ""
                st.markdown(f"<div class='clarte-card'><strong>{escape(target['label'])}</strong><span>{escape(target['code'])} · Retenu en séance</span><small>{escape(origin)}{(' · ' + escape(target['source_date'])) if target['source_date'] else ''}{escape(version)}</small></div>", unsafe_allow_html=True)
                if target.get("definition") or target.get("access_description"):
                    with st.expander(f"Définition et accès ROME · {target['code']}"):
                        if target.get("definition"):
                            st.write(target["definition"])
                        if target.get("access_description"):
                            st.markdown("**Description de l’accès au métier dans cette fiche**")
                            st.write(target["access_description"])
                            st.caption("Cette description présente un accès ou des formations courants. Elle ne prouve pas qu’un diplôme est légalement obligatoire. Vérifiez toute obligation avec une source officielle distincte.")
                context = rome_interest_context(target["code"])
                if context:
                    st.caption(f"Repère d’intérêt de la fiche : RIASEC {context['riasec_code']} · {context['source_label']}")
                    st.caption("À discuter avec le profil PIP du bénéficiaire. Ce repère ne mesure ni compétence ni aptitude.")
    if proposals:
        st.markdown("##### À examiner avec le bénéficiaire")
        for target in proposals:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"**{escape(target['label'])}**  \n`{escape(target['code'])}`")
                if c2.button("Retenir ce métier", key=f"rome_accept_{target['id']}", type="primary", use_container_width=True):
                    try:
                        decide_rome_target(ctx, case_id, target["id"], accept=True)
                        st.rerun()
                    except RomeCatalogError as exc:
                        st.error(str(exc))
                if c3.button("Écarter", key=f"rome_reject_{target['id']}", use_container_width=True):
                    decide_rome_target(ctx, case_id, target["id"], accept=False)
                    st.rerun()
    if not active and not proposals:
        st.info("Aucun métier n’est encore retenu. La fiche doit être examinée et confirmée avec le bénéficiaire.")
    st.caption("Maximum trois métiers actifs. Le choix reste celui du bénéficiaire ; le chargement d’une fiche ne vaut pas sélection.")


def _experience_label(item) -> str:
    period = f" · {item.period}" if item.period else ""
    kind = {"EMPLOI": "Expérience", "ETUDE": "Études", "FORMATION": "Formation",
            "AUTOFORMATION": "Apprentissage personnel", "AUTRE": "Autre parcours"}.get(item.kind, item.kind)
    return f"{kind} — {item.title}{period}"


def render_rome_matching(ctx, case_id: str) -> None:
    import streamlit as st
    st.markdown("#### 2 — Rapprocher les attendus ROME du parcours, en séance")
    st.info("L’accompagnateur conduit le travail à l’écran avec le bénéficiaire : on sélectionne plusieurs attendus, on retrouve les expériences qui les étayent et on discute les incertitudes. L’IA prépare des pistes ; elle ne valide aucun acquis.")
    with st.expander("Aide de séance — sélectionner, rapprocher et qualifier un attendu", expanded=False):
        st.markdown(
            """
            1. Travaillez **un métier ROME à la fois** et cochez les savoirs ou compétences à examiner ensemble.
            2. Pour chaque attendu, reliez une ou plusieurs preuves du parcours : emploi, études **avec ou sans diplôme**, formation ou apprentissage personnel.
            3. Choisissez le statut après l’échange : acquis étayé, à confirmer, non documenté ou à développer. « Non documenté » signifie que l’information manque ; cela ne signifie pas que le bénéficiaire ne sait pas faire.
            4. Si vous retenez « acquis étayé », choisissez aussi le niveau discuté pour **cet attendu précis** : 1 pratique encadrée/contribution, 2 maîtrise autonome, 3 pilotage/expertise/transmission. Ne le déduisez pas du titre du poste ou d’un diplôme.
            5. Un diplôme ou titre n’est une condition obligatoire que si une source officielle le confirme. Une exigence fréquente dans les offres reste une attente d’employeur à vérifier, pas une obligation légale.

            Les propositions de l’IA sont des pistes pour faciliter l’échange ; l’accompagnateur et le bénéficiaire confrontent les faits, puis l’accompagnateur enregistre la revue.
            """
        )
    try:
        workspace = read_rome_matching_workspace(ctx, case_id)
    except Exception:
        st.error("L’atelier n’est pas disponible pour cette session accompagnateur.")
        return
    if not workspace.targets:
        st.warning("Aucun métier ROME n’a encore été confirmé. Commencez par choisir les métiers à étudier.")
        return
    labels = {f"{x.code} — {x.label}": x.id for x in workspace.targets}
    chosen = st.selectbox("Métier travaillé en séance", list(labels), key="rome_matching_target")
    target_id = labels[chosen]
    target = next(x for x in workspace.targets if x.id == target_id)
    fingerprint = dict(workspace.fingerprint_by_target)[target_id]
    if target.source_date:
        st.caption(f"Référence France Travail · fiche consultée le {target.source_date}" + (f" · {target.source_version}" if target.source_version else ""))
    else:
        st.warning("Aucune fiche ROME versionnée n’est liée à ce métier ; l’analyse est bloquée tant que les attendus officiels ne sont pas chargés.")
        return
    if not target.items:
        st.warning("La fiche est présente, mais ses savoirs et compétences n’ont pas été reconnus dans son contenu. Le rapprochement est bloqué pour éviter d’inventer la liste.")
        return
    with st.expander("Ajouter un élément de parcours évoqué en séance", expanded=not bool(workspace.experiences)):
        st.caption("Ajoutez en séance un élément qui peut étayer un savoir : emploi, études (même sans diplôme), formation ou apprentissage personnel. Chaque ajout est marqué comme apport de séance à confirmer ; il ne devient pas automatiquement un acquis.")
        with st.form(f"rome_session_experience_{case_id}"):
            kind = st.selectbox("Nature de l’élément de parcours", ["EMPLOI", "ETUDE", "FORMATION", "AUTOFORMATION", "AUTRE"],
                format_func=lambda value: {"EMPLOI": "Expérience professionnelle", "ETUDE": "Études (avec ou sans diplôme)",
                    "FORMATION": "Formation", "AUTOFORMATION": "Apprentissage personnel / autodidacte", "AUTRE": "Autre élément de parcours"}[value])
            title = st.text_input("Intitulé de l’élément de parcours", max_chars=240)
            e1, e2 = st.columns(2)
            organization = e1.text_input("Structure / organisme (facultatif)", max_chars=240)
            period_start = e2.text_input("Début (facultatif)", max_chars=20, placeholder="AAAA-MM")
            e3, e4 = st.columns(2)
            period_end = e3.text_input("Fin (facultatif)", max_chars=20, placeholder="AAAA-MM ou en cours")
            context_text = e4.text_input("Contexte / secteur (facultatif)", max_chars=2400)
            activities = st.text_area("Activités, contenus étudiés ou missions", max_chars=2400, height=90)
            autonomy = st.text_area("Responsabilités et autonomie", max_chars=1200, height=70)
            achievements = st.text_area("Réalisations ou résultats", max_chars=2400, height=70)
            tools = st.text_area("Outils, méthodes ou référentiels", max_chars=1200, height=60)
            knowledge = st.text_area("Savoirs et savoir-faire mobilisés", max_chars=1600, height=70)
            level_label_to_value = {
                "À préciser avec le bénéficiaire": None,
                "1 — Pratique encadrée / contribution": 1,
                "2 — Maîtrise autonome": 2,
                "3 — Pilotage, expertise ou transmission": 3,
            }
            level_label = st.selectbox(
                "Niveau d’exercice discuté pour cette expérience",
                list(level_label_to_value),
                help="Ce repère décrit les faits observés dans cette expérience. Il ne se déduit pas du titre du poste et ne classe pas la personne.",
            )
            add_experience = st.form_submit_button("Ajouter cet apport de séance au parcours", use_container_width=True)
        if add_experience:
            try:
                add_session_experience(ctx, case_id, title=title, kind=kind, organization=organization,
                    period_start=period_start, period_end=period_end, context=context_text,
                    activities=activities, autonomy=autonomy, achievements=achievements,
                    tools=tools, knowledge=knowledge, level_of_exercise=level_label_to_value[level_label])
                st.success("Élément ajouté au parcours avec la provenance « apport de séance ». Le niveau discuté est conservé avec cette expérience, sans être inféré du titre du poste.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc) if isinstance(exc, ValueError) else "L’élément de parcours n’a pas pu être enregistré.")
    if not workspace.experiences:
        st.warning("Aucun élément structuré du parcours n’est encore disponible. Complétez une carte du parcours ou ajoutez un apport de séance avant le rapprochement.")
        return

    latest = next((x for x in workspace.analyses if x["job_target_id"] == target_id), None)
    current_review = next((review for jobid, fp, review in workspace.current_reviews
                           if jobid == target_id and fp == fingerprint), None)
    saved_review_items = {row.get("rome_item_key"): row for row in (current_review or {}).get("items", [])}
    query = st.text_input("Filtrer les attendus ROME", key=f"rome_matching_filter_{target_id}", placeholder="Ex. gestion, client, réglementation…")
    categories = {category: [x for x in target.items if x.category == category and (not query or query.casefold() in (x.label + " " + x.hierarchy).casefold())]
                  for category in _CATEGORY_LABELS}
    for category, title in _CATEGORY_LABELS.items():
        rows = categories[category]
        if not rows:
            continue
        with st.expander(f"{title} · {len(rows)}", expanded=(category == "SAVOIR")):
            pick_cols = st.columns(2)
            for index, item in enumerate(rows):
                with pick_cols[index % 2]:
                    pick_key = f"rome_pick_{target_id}_{item.key}"
                    st.session_state.setdefault(pick_key, item.key in saved_review_items)
                    st.checkbox(item.label, key=pick_key, help=item.hierarchy or None)
    selected = [item for item in target.items if st.session_state.get(f"rome_pick_{target_id}_{item.key}", False)]
    st.markdown(f"**Sélection en cours : {len(selected)} attendu(s)**")
    selected_keys = {item.key for item in selected}
    analyzed_keys = set((latest or {}).get("result", {}).get("_source", {}).get("item_keys", []))
    current_analysis = (latest if latest and latest["current"]
                        and latest["source_fingerprint"] == fingerprint
                        and analyzed_keys == selected_keys else None)
    if current_analysis:
        st.markdown("##### Synthèse des propositions IA — à discuter, non validées")
        proposals = {p["rome_item_key"]: p for p in current_analysis["result"].get("propositions", [])}
        counts = (
            ("Pistes d’acquis", sum(p["statut_propose"] == "ACQUIS_POTENTIEL" for p in proposals.values())),
            ("À confirmer", sum(p["statut_propose"] == "A_CONFIRMER" for p in proposals.values())),
            ("Non documentés", sum(p["statut_propose"] == "NON_DOCUMENTE" for p in proposals.values())),
            ("À développer", sum(p["statut_propose"] == "A_DEVELOPPER" for p in proposals.values())),
        )
        cols = st.columns(4)
        for col, (label, count) in zip(cols, counts):
            col.markdown(f"<div class='clarte-kpi'><span>{escape(label)}</span><strong>{count}</strong><small>Proposition IA</small></div>", unsafe_allow_html=True)
    elif current_review and current_review.get("items"):
        st.markdown("##### Synthèse de la dernière revue de séance")
        counts = tuple((label, sum(row["status"] == status for row in current_review["items"])) for label, status in (
            ("Acquis étayés", "ACQUIS_ETAYE"), ("À confirmer", "A_CONFIRMER"),
            ("Non documentés", "NON_DOCUMENTE"), ("À développer", "A_DEVELOPPER")))
        cols = st.columns(4)
        for col, (label, count) in zip(cols, counts):
            col.markdown(f"<div class='clarte-kpi'><span>{escape(label)}</span><strong>{count}</strong><small>Revue humaine</small></div>", unsafe_allow_html=True)
    if len(selected) > 40:
        st.warning("Pour garder un échange lisible, l’IA traite au plus 40 attendus par analyse. Vous pouvez enregistrer une sélection plus large manuellement.")
    if selected:
        ai_col, explain_col = st.columns([1, 2])
        with ai_col:
            consent_fingerprint = hashlib.sha256(
                (fingerprint + "|" + "|".join(sorted(selected_keys))).encode("utf-8")
            ).hexdigest()[:16]
            informed = st.checkbox(
                "Le bénéficiaire a été informé et accepte cet envoi de données utiles à l’analyse.",
                key=f"rome_matching_ai_consent_{case_id}_{target_id}_{consent_fingerprint}",
            )
            if st.button("Préparer les rapprochements avec l’IA", type="primary", key=f"rome_matching_ai_{target_id}", use_container_width=True, disabled=not ai_ready() or not selected or len(selected) > 40 or not informed):
                try:
                    with st.spinner("Analyse des attendus et des expériences en cours…"):
                        run_rome_matching_analysis(ctx, case_id, target_id, selected_item_keys=[item.key for item in selected])
                    st.success("Propositions IA prêtes à discuter. Rien n’a été validé automatiquement.")
                    st.rerun()
                except (RomeMatchingError, OrientationConflict) as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("L’analyse IA n’a pas abouti. Le détail technique n’est pas affiché dans le dossier.")
            if not ai_ready():
                st.caption("L’IA partagée Clarté360 n’est pas configurée dans cette candidate.")
        with explain_col:
            st.caption("L’analyse transmet les attendus ROME et des faits de parcours nécessaires au rapprochement. Elle n’envoie ni le CV brut ni les identifiants du dossier ; seuls les attendus retenus et les éléments de parcours utiles sont transmis. Évitez d’inscrire des données personnelles dans les descriptions.")
        if latest and not latest["current"]:
            st.warning("La proposition IA précédente est périmée, car la fiche ROME ou le parcours a changé. Elle ne sera pas proposée à l’enregistrement.")
        elif latest and analyzed_keys != selected_keys:
            st.info("La sélection d’attendus a changé depuis la dernière analyse. Relancez l’IA pour préparer des pistes sur cette sélection.")
        if current_analysis:
            st.markdown("##### Détail des pistes IA à confronter à l’échange")
            for row in current_analysis["result"].get("propositions", []):
                item = next((x for x in target.items if x.key == row["rome_item_key"]), None)
                if item:
                    with st.expander(f"{item.label} — piste IA : {row['statut_propose'].replace('_', ' ').lower()}"):
                        st.write(row["raisonnement"])
                        st.markdown(f"**Question possible en séance :** {row['question_en_seance']}")
                        refs = [x for x in workspace.experiences if x.id in row["experience_refs"]]
                        if refs:
                            st.caption("Expériences suggérées : " + "; ".join(_experience_label(x) for x in refs))
                        st.caption("À discuter et valider ensemble. Cette proposition n’est pas un acquis enregistré.")
            if current_analysis["result"].get("incertitudes"):
                with st.expander("Incertitudes signalées par l’IA"):
                    for uncertainty in current_analysis["result"]["incertitudes"]:
                        st.write(f"• {uncertainty}")
        else:
            proposals = {}
            st.caption("L’IA peut préparer des correspondances avec les expériences. Vous pouvez aussi conduire et enregistrer le rapprochement manuellement.")

    if selected:
        with st.form(f"rome_matching_review_form_{target_id}"):
            experience_options = {_experience_label(item): item.id for item in workspace.experiences}
            rows = []
            for item in selected:
                proposal = proposals.get(item.key, {})
                st.markdown(f"##### {item.label}")
                if proposal:
                    st.caption(f"Piste IA : {proposal['raisonnement']}")
                    if proposal.get("question_en_seance"):
                        st.caption(f"Question à discuter : {proposal['question_en_seance']}")
                statuses = list(MATCH_STATUSES)
                proposed_ui = "A_CONFIRMER"
                if proposal.get("statut_propose") == "NON_DOCUMENTE": proposed_ui = "NON_DOCUMENTE"
                elif proposal.get("statut_propose") == "A_DEVELOPPER": proposed_ui = "A_DEVELOPPER"
                saved = saved_review_items.get(item.key, {})
                default_status = saved.get("status") if saved.get("status") in statuses else proposed_ui
                status = st.selectbox("Statut après échange", statuses, index=statuses.index(default_status),
                                      format_func=lambda code: MATCH_STATUSES[code], key=f"rome_status_{target_id}_{item.key}")
                saved_experience_ids = {e.get("experience_id") for e in saved.get("experiences", []) if e.get("experience_id")}
                default_experiences = [label for label, exp_id in experience_options.items()
                                       if exp_id in saved_experience_ids] if saved else [
                    label for label, exp_id in experience_options.items()
                    if proposal and exp_id in proposal.get("experience_refs", [])]
                associated = st.multiselect("Élément(s) du parcours qui étayent ce savoir", list(experience_options),
                    default=default_experiences,
                    key=f"rome_experiences_{target_id}_{item.key}")
                level_labels = {None: "À préciser avec le bénéficiaire",
                    **{level: f"{level} — {description}" for level, description in EXERCISE_LEVELS.items()}}
                saved_level = saved.get("exercise_level") if saved else None
                level_default = level_labels.get(saved_level, level_labels[None])
                exercise_level_label = st.selectbox(
                    "Niveau d’exercice de ce savoir, discuté en séance",
                    list(level_labels.values()),
                    index=list(level_labels.values()).index(level_default),
                    help="Choisissez un niveau pour ce savoir précis. Il est discuté avec le bénéficiaire et ne se déduit ni du métier, ni du diplôme, ni de l’IA.",
                    key=f"rome_level_{target_id}_{item.key}",
                )
                rationale = st.text_area("Précision utile issue de l’échange (facultatif)", value=saved.get("rationale", ""), max_chars=1200,
                                         key=f"rome_rationale_{target_id}_{item.key}", height=70)
                rows.append({"rome_item_key": item.key, "status": status,
                             "experience_ids": [experience_options[x] for x in associated], "rationale": rationale,
                             "exercise_level": next((level for level, label in level_labels.items()
                                                     if label == exercise_level_label), None)})
            submitted = st.form_submit_button("Enregistrer le rapprochement de la sélection", type="primary", use_container_width=True)
        if submitted:
            try:
                saved = save_rome_matching_review(ctx, case_id, target_id, rows,
                    analysis_id=current_analysis["analysis_id"] if current_analysis else None)
                st.success(f"{saved['items_count']} rapprochement(s) enregistré(s) en version {saved['version_no']}.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc) if isinstance(exc, (ValueError, RomeMatchingError)) else "L’enregistrement a échoué ; la version du parcours ou de la fiche a peut-être changé.")
    else:
        st.info("Cochez un ou plusieurs savoirs ou compétences, puis reliez chacun à une ou plusieurs expériences pour enregistrer la revue de séance.")

    if current_review:
        with st.expander("Rapprochements enregistrés — résultat de séance", expanded=False):
            st.caption("Version conservée dans l’historique. L’accompagnateur peut rouvrir la revue si un échange ultérieur la fait évoluer.")
            for row in current_review.get("items", []):
                st.markdown(f"**{row['rome_label']}** — {MATCH_STATUSES.get(row['status'], row['status'])}")
                if row.get("experiences"):
                    st.caption("Étayé par : " + "; ".join(f"{e['title']} ({e['period']})" if e.get("period") else e['title'] for e in row["experiences"]))
                if row.get("rationale"):
                    st.write(row["rationale"])


def render_rome_clarification(ctx, case_id: str) -> None:
    """Carry unresolved ROME items into the next, focused clarification phase."""
    import streamlit as st
    st.markdown("#### Points à confirmer avec le bénéficiaire")
    st.caption("Cette étape reprend les attendus restés incertains après l’atelier. Elle sert d’abord à clarifier en séance ; une recherche externe n’est confiée au bénéficiaire que si elle peut réellement aider à décider.")
    try:
        workspace = read_rome_matching_workspace(ctx, case_id)
    except Exception:
        st.error("Les points de rapprochement ne peuvent pas être lus dans cette session accompagnateur.")
        return
    fingerprints = dict(workspace.fingerprint_by_target)
    pending = []
    for target_id, fingerprint, review in workspace.current_reviews:
        if fingerprints.get(target_id) != fingerprint:
            continue
        target = next((x for x in workspace.targets if x.id == target_id), None)
        if not target:
            continue
        for row in review.get("items", []):
            if row.get("status") not in {"A_CONFIRMER", "NON_DOCUMENTE"}:
                continue
            ai_question = (row.get("ai_proposal") or {}).get("question_en_seance", "")
            question = ai_question or "Quelle situation concrète de votre parcours pourrait éclairer cet attendu ?"
            pending.append({"target": target, "row": row, "question": question})
    if not pending:
        st.success("Aucun point ROME marqué « à confirmer » ou « non documenté » dans la dernière revue en cours.")
        st.caption("Les points « à développer » restent un choix du bénéficiaire et peuvent être repris lors de la comparaison ou du plan d’action.")
        return
    first = pending[0]
    st.markdown(
        f"<div class='clarte-question'><span>QUESTION 1 / {len(pending)} · {first['target'].code}</span>"
        f"<strong>{escape(first['question'])}</strong><small>{escape(first['row']['rome_label'])} — {escape(first['row']['status'].replace('_', ' ').title())}</small></div>",
        unsafe_allow_html=True,
    )
    with st.expander(f"Voir les {len(pending)} points à clarifier", expanded=False):
        for index, item in enumerate(pending, 1):
            st.markdown(f"**{index}. {escape(item['target'].code)} — {escape(item['row']['rome_label'])}**")
            st.write(item["question"])
            if item["row"].get("experiences"):
                st.caption("Éléments du parcours déjà rapprochés : " + "; ".join(
                    e["title"] for e in item["row"]["experiences"] if e.get("title")))
    st.info("Après l’échange, revenez à la phase 3 pour mettre à jour le statut et les éléments du parcours. Avant la comparaison, une action d’investigation ciblée sera reliée à chaque métier ROME retenu ; choisissez avec le bénéficiaire la question utile. Les sources ou API particulières à consulter ne sont pas imposées.")


def render_rome_investigations(ctx, case_id: str) -> None:
    """Assign only useful field checks, then review beneficiary findings."""
    import streamlit as st
    if st.session_state.pop("clear_go23_investigation_form", False):
        for key in ("go23_investigation_goal", "go23_investigation_target", "go23_investigation_type"):
            st.session_state.pop(key, None)
    prefill = st.session_state.get("go23_investigation_prefill")
    if prefill:
        st.session_state.setdefault("go23_investigation_target", prefill["target_option"])
        st.session_state.setdefault("go23_investigation_type", prefill["task_type"])
        st.session_state.setdefault("go23_investigation_goal", prefill["goal"])
    else:
        st.session_state.setdefault("go23_investigation_target", "Aucun métier ROME associé")
        st.session_state.setdefault("go23_investigation_type", next(iter(TASK_TYPES)))
        st.session_state.setdefault("go23_investigation_goal", "")
    st.markdown("#### Enquêtes et vérifications utiles au projet")
    st.info("Avant de comparer les pistes, une investigation ciblée est confiée pour chaque métier ROME retenu, puis son retour est débriefé. L’accompagnateur choisit avec le bénéficiaire la question utile. Les liens et API sont des ressources possibles : aucune liste de sites n’est à parcourir systématiquement.")
    try:
        tasks = read_intersession_tasks(ctx, case_id)
    except Exception:
        st.error("Les actions d’investigation ne peuvent pas être lues pour cette session.")
        return
    try:
        workspace = read_rome_matching_workspace(ctx, case_id)
        fingerprints = dict(workspace.fingerprint_by_target)
        targets_by_id = {target.id: target for target in workspace.targets}
        unresolved = []
        for target_id, fingerprint, review in workspace.current_reviews:
            if fingerprints.get(target_id) != fingerprint or target_id not in targets_by_id:
                continue
            target = targets_by_id[target_id]
            for row in review.get("items", []):
                if row.get("status") not in {"A_CONFIRMER", "NON_DOCUMENTE"}:
                    continue
                label = f"{target.code} — {target.label} · {row.get('category', 'ROME')} · {row['rome_label']}"
                question = str((row.get("ai_proposal") or {}).get("question_en_seance", "") or "").strip()[:700]
                unresolved.append({"label": label, "target_id": target.id, "code": target.code,
                    "job_label": target.label, "skill": row["rome_label"], "question": question})
    except Exception:
        unresolved = []

    if unresolved:
        with st.expander("Préparer une investigation depuis un point ROME à vérifier", expanded=bool(prefill)):
            st.caption("Les points « à confirmer » ou « non documenté » viennent du rapprochement fait en séance. Choisissez-en un si une vérification externe peut aider le bénéficiaire à comprendre ou décider. La mission reste à relire et à transmettre par l’accompagnateur.")
            prompt_options = {item["label"]: item for item in unresolved}
            selected_label = st.selectbox("Point de l’analyse à approfondir", ["Choisir un point"] + list(prompt_options),
                key="go23_investigation_source")
            if selected_label != "Choisir un point":
                selected = prompt_options[selected_label]
                if selected.get("question"):
                    st.info("Question issue de la relecture : " + selected["question"])
                if st.button("Préparer une mission à partir de ce point", key="go23_prepare_investigation"):
                    question = selected.get("question") or "Quelles situations professionnelles mobilisent réellement ce savoir-faire ?"
                    mission_goal = (f"Pour le métier {selected['code']} — {selected['job_label']}, vérifier comment « {selected['skill']} » "
                                    f"est réellement mobilisé. Point de départ de l'analyse : {question} "
                                    "Relever une source ou un échange professionnel, les faits observés et ce que cela change ou laisse à vérifier dans le projet.")[:1600]
                    st.session_state["go23_investigation_prefill"] = {
                        "target_id": selected["target_id"], "target_label": selected_label,
                        "target_option": f"{selected['code']} — {selected['job_label']}",
                        "task_type": "ENQUETE_METIER",
                        "goal": mission_goal,
                    }
                    st.session_state["go23_investigation_target"] = f"{selected['code']} — {selected['job_label']}"
                    st.session_state["go23_investigation_type"] = "ENQUETE_METIER"
                    st.session_state["go23_investigation_goal"] = mission_goal
                    st.rerun()
    if tasks:
        st.markdown("##### Actions confiées et retours reçus")
        for task in tasks:
            state_label = {"PUBLIEE": "À faire", "EN_COURS": "En cours", "SOUMISE": "Retour reçu · à débriefer",
                           "A_DEBRIEFER": "À débriefer", "CLOTUREE": "Débriefé"}.get(task["state"], task["state"])
            with st.container(border=True):
                st.markdown(f"**{task['task_type_label']}** · {state_label}")
                if task.get("job_target_label"):
                    st.caption(f"Métier ROME concerné : {task.get('job_target_code')} — {task['job_target_label']}")
                st.write(task["goal"])
                response = task.get("response")
                if response:
                    st.caption(f"Source : {response['source']} · consultée le {response['consulted_on']}")
                    st.markdown("**Ce que le bénéficiaire a appris**")
                    st.write(response["learned"])
                    st.markdown("**Effet sur le projet**")
                    st.write(response["project_impact"])
                if task["state"] in {"SOUMISE", "A_DEBRIEFER"}:
                    if st.button("Marquer le débrief comme réalisé", key=f"is_close_{task['task_id']}", use_container_width=True):
                        try:
                            close_intersession_task(ctx, case_id, task["task_id"])
                            st.success("Débrief enregistré.")
                            st.rerun()
                        except Exception:
                            st.error("Le débrief n’a pas pu être enregistré.")
    with st.expander("Confier une nouvelle investigation", expanded=bool(prefill) or not bool(tasks)):
        st.caption("Formulez une question précise. Avant la comparaison, chaque métier ROME retenu doit être relié à au moins une action dont le retour aura été débriefé. Les ressources ou API particulières à consulter restent au choix selon la question ; le bénéficiaire renseigne toujours le questionnaire de retour.")
        type_options = list(TASK_TYPES)
        with st.form(f"intersession_create_{case_id}"):
            try:
                active_targets = [x for x in read_rome_targets(ctx, case_id) if x["status"] == "ACTIVE"]
            except Exception:
                active_targets = []
            target_options = {"Aucun métier ROME associé": None}
            target_options.update({f"{x['code']} — {x['label']}": x for x in active_targets})
            related_label = st.selectbox("Métier ROME concerné par cette investigation", list(target_options),
                help="Choisissez le métier étudié pour retrouver ensuite l'enquête et son retour au bon endroit.",
                key="go23_investigation_target")
            task_type = st.selectbox("Nature de la vérification", type_options,
                format_func=lambda value: TASK_TYPES[value], key="go23_investigation_type")
            goal = st.text_area("Question ou objectif confié au bénéficiaire",
                max_chars=1600, height=120, key="go23_investigation_goal",
                placeholder="Ex. Comparer deux offres de comptable dans le secteur visé et relever les compétences et conditions d’accès réellement demandées.")
            submitted = st.form_submit_button("Transmettre cette action au bénéficiaire", type="primary", use_container_width=True)
        if submitted:
            try:
                if len(goal.strip()) < 12:
                    raise ValueError("Précisez une action utile en 12 à 1 600 caractères.")
                related = target_options[related_label]
                create_intersession_task(ctx, case_id, task_type=task_type,
                    job_target_id=related["id"] if related else None, goal=goal.strip())
                st.session_state.pop("go23_investigation_prefill", None)
                st.session_state["clear_go23_investigation_form"] = True
                st.success("Action publiée dans « Mes actions » pour le bénéficiaire.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("L’action n’a pas pu être publiée.")
