from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import escape

from clarte360_cp.application.beneficiary import BeneficiaryHomeView, build_beneficiary_home
from clarte360_cp.framework.navigation import set_page
from clarte360_cp.ui.live_sync import render_live_sync_status
from clarte360_cp.ui.spec import BENEFICIARY_STAGE_BY_PHASE, beneficiary_phase_page
from clarte360_cp.ui.orientation import render_beneficiary_orientation
from clarte360_cp.ui.preparation import render_beneficiary_preparation
from clarte360_cp.ui.research_resources import RESOURCE_GROUPS, render_research_resources
from clarte360_cp.application.preparation import read_preparation
from clarte360_cp.application.intersession import read_intersession_tasks, save_intersession_draft, submit_intersession_response
from clarte360_cp.application.go24 import read_action_plan, respond_to_action_plan
from clarte360_cp.application.conclusion import read_conclusion, respond_to_conclusion, submit_followup_response
from clarte360_cp.application.career_feedback import respond_to_career_phase, CareerFeedbackConflict
from clarte360_cp.application.rome_interest_context import rome_interest_context


FRIENDLY_PHASE = {
    0: "Mon parcours professionnel",
    1: "Mes pistes",
    2: "Les métiers étudiés",
    3: "Ce que mon parcours montre déjà",
    4: "Mes points à préciser",
    5: "Vérifier la réalité",
    6: "Comparer mes pistes",
    7: "Mon projet",
    8: "Mon plan d'action",
    9: "Mes résultats détaillés",
    10: "Ma synthèse de bilan",
    11: "La suite de mon bilan",
}

PHASE_HELP = {
    0: "Le parcours enrichi préparé en séance à partir de votre CV, de vos échanges et de l'assistance IA.",
    1: "Les pistes que vous avez exprimées ou accepté d'explorer.",
    2: "Les métiers de référence que vous avez choisi d'étudier avec votre accompagnateur.",
    3: "Une lecture synthétique de ce que votre parcours permet déjà d'étayer face aux métiers étudiés.",
    4: "Les quelques points qui méritent d'être précisés avant de poursuivre l'analyse.",
    5: "Les éléments de terrain, conditions d'accès et vérifications utiles pour confronter le projet au réel.",
    6: "La comparaison qualitative des pistes, sans score ni classement automatique.",
    7: "Le projet que vous retenez, avec ses raisons, conditions de réussite et points de vigilance.",
    8: "Les actions concrètes à engager pour mettre le projet en œuvre.",
    9: "La restitution détaillée de ce qui ressort du bilan et de votre parcours.",
    10: "Le document de synthèse final, distinct des résultats détaillés.",
    11: "Les documents remis, les repères de suite et le suivi Clarté360.",
}

DOC_LABELS = {
    "APS_OBJECTIF": "Objectif de mon bilan",
    "BOUSSOLE_VALEURS": "Boussole des valeurs",
    "MOTEURS_PRO": "Moteurs professionnels",
    "PREFERENCES_PRO": "Préférences professionnelles",
    "IPIP_REPORT": "Profil de fonctionnement professionnel",
    "PIP_REPORT": "PIP RIASEC",
    "CV_SOURCE": "CV source",
    "PARCOURS_PRO_ENRICHI": "Mon parcours professionnel enrichi",
    "PLAN_ACTION_FINAL": "Plan d'action",
    "RESULTATS_DETAILLES_FINAL": "Résultats détaillés",
    "SYNTHESE_FINALE": "Synthèse de bilan",
}


@dataclass(frozen=True)
class BeneficiaryNextAction:
    title: str
    detail: str
    page: str
    duration: str | None = None


def _go(page: str) -> None:
    import streamlit as st
    set_page(st.session_state, page)
    st.rerun()


def _button(label: str, page: str, *, key: str, primary: bool = False, disabled: bool = False) -> None:
    import streamlit as st
    if st.button(label, key=key, type="primary" if primary else "secondary", use_container_width=True, disabled=disabled):
        _go(page)


def _phase_states(view: BeneficiaryHomeView) -> dict[int, str]:
    return dict(view.snapshot.phase_states)


def _beneficiary_state_label(state: str | None) -> str:
    mapping = {
        "NON_DISPONIBLE": "Pas encore travaillé",
        "DISPONIBLE": "À venir",
        "EN_COURS": "En cours avec mon accompagnateur",
        "EN_ATTENTE_BENEFICIAIRE": "À relire / confirmer",
        "EN_ATTENTE_ACCOMPAGNATEUR": "En attente de mon accompagnateur",
        "VALIDEE": "Validé",
        "REOUVERTE": "Mis à jour — à revoir",
        "FIGEE_CLOTURE": "Terminé",
    }
    return mapping.get(state or "", (state or "À venir").replace("_", " ").title())


def _next_action(view: BeneficiaryHomeView, preparation=None) -> BeneficiaryNextAction:
    # La préparation prescrite précède toute tâche de démonstration ou phase ultérieure.
    if preparation is not None and preparation.invitation_open and preparation.active_answers is None:
        return BeneficiaryNextAction(
            "Répondre à mes idées et à mes repères",
            "D’abord mes idées professionnelles, puis mes repères personnels. Je peux revenir en arrière et reprendre avant l’envoi définitif.",
            "b_preparation",
        )
    if preparation is not None and preparation.invitation_open and preparation.active_answers is not None:
        return BeneficiaryNextAction(
            "Mon questionnaire a bien été transmis",
            "Mes réponses seront reprises avec mon accompagnateur. Je n’ai pas besoin de remplir une nouvelle fois ce questionnaire.",
            "b_home",
        )
    for task in view.snapshot.tasks:
        if task.state in {"PUBLIEE", "EN_COURS"}:
            return BeneficiaryNextAction(
                "Faire ma vérification en cours",
                (f"{task.job_label} — {task.goal}" if task.job_label else task.goal),
                "b_intersession",
                "5 à 10 min",
            )
    if view.snapshot.orientation_published_version is not None and view.snapshot.orientation_feedback is None:
        return BeneficiaryNextAction(
            "Relire mes idées et premières directions",
            "Une version de notre travail commun est prête pour votre confirmation ou une demande de correction.",
            "b_orientation",
        )
    for phase_no, state in view.snapshot.phase_states:
        if state == "EN_ATTENTE_BENEFICIAIRE":
            return BeneficiaryNextAction(
                FRIENDLY_PHASE.get(phase_no, "Relire avec mon accompagnateur"),
                "Un résultat du travail réalisé ensemble est prêt pour votre lecture, votre confirmation ou une demande de correction.",
                beneficiary_phase_page(phase_no),
            )
    if view.snapshot.published_documents:
        return BeneficiaryNextAction(
            "Retrouver les résultats déjà partagés",
            "Vous pouvez relire à tout moment les résultats du travail réalisé avec votre accompagnateur.",
            "b_journey",
        )
    return BeneficiaryNextAction(
        "Rien à faire pour le moment",
        "Votre accompagnateur prépare la suite. Vous retrouverez ici votre prochaine action dès qu'elle sera prête.",
        "b_home",
    )


def render_header(ctx, view: BeneficiaryHomeView) -> None:
    import streamlit as st
    phase = view.snapshot.current_phase if view.snapshot.current_phase is not None else 0
    stage = BENEFICIARY_STAGE_BY_PHASE.get(phase, "Explorer")
    st.markdown(
        f"""
<div class="clarte-beneficiary-header">
  <div><strong>CLARTÉ360</strong><br><span>Compétences & Projets</span></div>
  <div><strong>Mon bilan</strong><br><span>{stage}</span></div>
  <div><strong>Dossier</strong><br><span>Actualisé en direct</span></div>
</div>
""",
        unsafe_allow_html=True,
    )
    render_live_sync_status(ctx, view.snapshot.case_id, compact=True)


def render_nav() -> None:
    import streamlit as st
    current = st.session_state.get("navigation_page", "b_home")
    items = (
        ("Accueil", "b_home"),
        ("Mon parcours", "b_journey"),
        ("Mes actions", "b_actions"),
        ("Mes documents", "b_documents"),
    )
    cols = st.columns(4)
    for col, (label, page) in zip(cols, items):
        with col:
            if st.button(label, key=f"bnav_{page}", type="primary" if current == page else "secondary", use_container_width=True):
                _go(page)


def render_stage_line(view: BeneficiaryHomeView) -> None:
    import streamlit as st
    phase = view.snapshot.current_phase if view.snapshot.current_phase is not None else 0
    current = BENEFICIARY_STAGE_BY_PHASE.get(phase, "Explorer")
    stages = ("Explorer", "Vérifier", "Choisir", "Agir", "Finaliser")
    bits = []
    for index, stage in enumerate(stages):
        cls = f"clarte-stage clarte-stage-{index}"
        if stage == current:
            cls += " clarte-stage-current"
        bits.append(f'<span class="{cls}">{stage}</span>')
    st.markdown('<div class="clarte-stage-line">' + '<span class="clarte-stage-sep">›</span>'.join(bits) + '</div>', unsafe_allow_html=True)


def _render_attention_counts(view: BeneficiaryHomeView) -> None:
    import streamlit as st
    st.markdown("### Ce qui demande mon attention")
    cols = st.columns(4)
    values = (
        ("À lire", view.to_read, "Résultats et documents partagés"),
        ("À faire", view.to_do, "Travaux hors séance"),
        ("À valider", view.to_validate, "Confirmations attendues"),
        ("Terminé", view.done, "Étapes ou tâches terminées"),
    )
    for col, (label, value, note) in zip(cols, values):
        with col:
            st.markdown(
                f"<div class='clarte-kpi'><span>{label}</span><strong>{value}</strong><small>{note}</small></div>",
                unsafe_allow_html=True,
            )


def render_home(ctx, view: BeneficiaryHomeView) -> None:
    import streamlit as st
    prep = read_preparation(ctx, view.snapshot.case_id)
    action = _next_action(view, prep)
    st.title("Mon bilan")
    st.caption("Votre espace conserve la trace lisible du travail réalisé avec votre accompagnateur. Vous pouvez relire chaque étape ; vous ne saisissez que lorsque cela vous est explicitement demandé.")
    if prep.invitation_open:
        if prep.active_answers is None:
            st.info("Votre questionnaire est disponible en deux parties : mes idées professionnelles, puis mes repères personnels. Aucune analyse par IA n’est faite pendant vos réponses.")
        else:
            st.success("Votre questionnaire personnel a été transmis. Sa version originale est conservée pour notre prochain entretien.")
            _button("Relire mes réponses", "b_preparation", key="ben_prep_review")
    render_stage_line(view)

    st.markdown(
        f"""
<div class="clarte-next-action clarte-beneficiary-next">
  <div class="clarte-eyebrow">MA PROCHAINE ACTION</div>
  <div class="clarte-next-title">{escape(action.title)}</div>
  <div class="clarte-muted">{escape(action.detail)}</div>
  {f'<div class="clarte-duration">Durée indicative : {escape(action.duration)}</div>' if action.duration else ''}
</div>
""",
        unsafe_allow_html=True,
    )
    if action.page != "b_home":
        next_label = "Commencer le questionnaire" if action.page == "b_preparation" else "Ouvrir ma prochaine action"
        _button(next_label, action.page, key="b_home_next", primary=True)

    _render_attention_counts(view)

    st.markdown("### Mon parcours")
    if view.snapshot.orientation_published_version is not None:
        st.write("**Mes idées, mes repères et mes premières directions** — version partagée")
        _button("Ouvrir ce résultat", "b_orientation", key="b_home_orientation")
    st.caption("Retrouvez les résultats du travail commun, étape après étape, même lorsque vous n'avez aucune action à réaliser.")
    states = _phase_states(view)
    for phase_no in range(3):
        state = states.get(phase_no)
        st.markdown(
            f"<div class='clarte-journey-card'><strong>{FRIENDLY_PHASE[phase_no]}</strong><span>{_beneficiary_state_label(state)}</span><small>{PHASE_HELP[phase_no]}</small></div>",
            unsafe_allow_html=True,
        )
    _button("Voir tout mon parcours", "b_journey", key="home_journey", primary=False)

    st.markdown("### Mes documents")
    if view.snapshot.published_documents:
        for doc in view.snapshot.published_documents[:3]:
            st.markdown(
                f"<div class='clarte-document-card'><strong>{DOC_LABELS.get(doc.artifact_type, doc.artifact_type.replace('_',' ').title())}</strong><span>{'Final' if doc.state in {'FINALISE','VALIDE'} else 'Disponible'}</span><small>Mis à disposition dans votre espace</small></div>",
                unsafe_allow_html=True,
            )
        _button("Voir tous mes documents", "b_documents", key="home_docs")
    else:
        st.info("Aucun document n'est disponible pour le moment.")


def render_journey(view: BeneficiaryHomeView) -> None:
    import streamlit as st
    st.title("Mon parcours")
    st.caption("Vous pouvez parcourir toutes les étapes de votre bilan. Les résultats partagés sont en lecture seule ; les étapes à venir restent visibles sans créer de fausse donnée.")
    states = _phase_states(view)
    st.markdown("### Pour commencer")
    if view.snapshot.orientation_published_version is None:
        st.info("Mes idées à moi et mes premiers repères seront visibles ici une fois partagés par mon accompagnateur.")
    else:
        st.write("**Mes idées à moi → Mes repères → Mes premières directions**")
        status = "À relire / confirmer" if view.snapshot.orientation_feedback is None else "Consulté et réponse enregistrée"
        st.caption(status)
        _button("Ouvrir mes premières directions", "b_orientation", key="b_journey_orientation")
    grouped = (
        ("Explorer", (0, 1, 2)),
        ("Vérifier", (3, 4, 5, 6)),
        ("Choisir", (7,)),
        ("Conclure", (9, 8, 10, 11)),
    )
    for group, phases in grouped:
        st.markdown(f"### {group}")
        cols = st.columns(2)
        for idx, phase_no in enumerate(phases):
            with cols[idx % 2]:
                state = states.get(phase_no)
                st.markdown(
                    f"<div class='clarte-journey-card'><strong>{FRIENDLY_PHASE[phase_no]}</strong><span>{_beneficiary_state_label(state)}</span><small>{PHASE_HELP[phase_no]}</small></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Ouvrir en lecture", key=f"journey_open_{phase_no}", use_container_width=True):
                    _go(beneficiary_phase_page(phase_no))


def render_actions(view: BeneficiaryHomeView) -> None:
    import streamlit as st
    st.title("Mes actions")
    st.caption("Cet espace contient uniquement ce que vous devez réellement faire vous-même, notamment les vérifications, rencontres, recherches ou retours préparés entre deux séances.")

    active = [t for t in view.snapshot.tasks if t.state in {"PUBLIEE", "EN_COURS"}]
    submitted = [t for t in view.snapshot.tasks if t.state in {"SOUMISE", "A_DEBRIEFER"}]
    closed = [t for t in view.snapshot.tasks if t.state == "CLOTUREE"]

    st.markdown("### À faire")
    if not active:
        st.success("Aucune action hors séance ne vous est demandée pour le moment.")
    for task in active:
        st.markdown(
            f"<div class='clarte-action-card'><strong>{escape(task.goal)}</strong><span>{'En cours' if task.state == 'EN_COURS' else 'À faire'}</span><small>{'Métier étudié : ' + escape(task.job_label) + ' · ' if task.job_label else ''}Cette action peut apporter une information utile à votre projet.</small></div>",
            unsafe_allow_html=True,
        )
        if st.button("Ouvrir cette action", key=f"actions_{task.task_id}", type="primary", use_container_width=True):
            st.session_state["intersession_task_id"] = task.task_id
            _go("b_intersession")

    if submitted:
        st.markdown("### Envoyé / à débriefer")
        for task in submitted:
            st.markdown(f"✓ **{task.goal}** — retour transmis à votre accompagnateur")
    if closed:
        st.markdown("### Terminé")
        for task in closed:
            st.markdown(f"✓ **{task.goal}**")

    st.markdown("---")
    render_research_resources()


def render_documents(ctx, case_id: str, view: BeneficiaryHomeView) -> None:
    import streamlit as st
    from clarte360_cp.connectors.gda_documents import GDAError, GDADocumentClient, load_gda_settings
    from clarte360_cp.repositories.db import build_engine, session_factory
    from clarte360_cp.repositories.gda_documents import list_linked_gda_documents, save_external_reference
    st.title("Mes documents")
    st.caption("Vous retrouvez uniquement les documents qui ont été mis à votre disposition. Les brouillons internes de l'accompagnateur restent invisibles.")
    if not view.snapshot.published_documents:
        st.info("Aucun document n'est disponible pour le moment.")
    for doc in view.snapshot.published_documents:
        label = DOC_LABELS.get(doc.artifact_type, doc.artifact_type.replace("_", " ").title())
        state = "Final" if doc.state in {"FINALISE", "VALIDE"} else "À relire" if doc.state == "PUBLIE_POUR_RELECTURE" else "Disponible"
        st.markdown(f"<div class='clarte-document-card'><strong>{escape(label)}</strong><span>{escape(state)}</span><small>Version {doc.version_no}</small></div>", unsafe_allow_html=True)
        st.caption("Le document reste dans l'espace partagé GDA.")
    settings = load_gda_settings(st.secrets)
    token = str(st.session_state.get("gda_launch_token", ""))
    if not settings.configured or not token:
        st.info("Vous pourrez déposer un document depuis cet écran quand Gestion des Actions aura activé le lien sécurisé.")
        return
    gda = GDADocumentClient(settings, token)
    engine = build_engine()
    with session_factory(engine)() as session:
        records = list_linked_gda_documents(session, case_id)
    if records:
        st.markdown("#### Documents partagés par votre accompagnateur")
        choices = {f"{doc.display_name} · v{doc.source_version}": doc for doc, link in records if link}
        for label, doc in choices.items():
            if st.button(f"Ouvrir · {label}", key=f"benef_gda_open_{doc.external_document_id}"):
                try:
                    metadata, content = gda.get_source(doc.source_ref)
                    st.download_button("Télécharger le document", content,
                        file_name=metadata.get("display_name") or "document", mime=metadata["mime_type"],
                        key=f"benef_gda_download_{doc.external_document_id}")
                except GDAError as exc:
                    st.error(str(exc))
    st.markdown("#### Déposer un document dans votre espace partagé")
    st.caption("Le document est transmis à Gestion des Actions, sans copie durable dans C&P. Votre accompagnateur le reliera ensuite au besoin du bilan.")
    upload = st.file_uploader("Choisir un fichier", key="benef_gda_upload")
    if st.button("Déposer dans mon espace", key="benef_gda_upload_btn", disabled=upload is None):
        try:
            item = gda.put_unlinked(upload.name, upload.getvalue(), mime_type=upload.type)
            with session_factory(engine)() as session:
                save_external_reference(session, ctx, case_id, item)
            st.success("Document déposé dans l’espace partagé. Votre accompagnateur pourra le relier au bilan.")
            st.rerun()
        except GDAError as exc:
            st.error(str(exc))


def render_category(view: BeneficiaryHomeView, category: str) -> None:
    """Pages historiques conservées pour compatibilité de navigation RC1 ; la RC2 privilégie Mon parcours / Mes actions."""
    import streamlit as st
    if category == "read":
        st.title("À lire")
        st.caption("Documents et informations prêts pour vous.")
        if not view.snapshot.published_documents:
            st.success("Rien à lire pour le moment.")
        for doc in view.snapshot.published_documents:
            st.write(f"**{DOC_LABELS.get(doc.artifact_type, doc.artifact_type.replace('_',' ').title())}**")
            _button("Ouvrir", "b_documents", key=f"read_{doc.artifact_id}")
    elif category == "do":
        render_actions(view)
        return
    elif category == "validate":
        st.title("À valider")
        pending = [phase for phase, state in view.snapshot.phase_states if state == "EN_ATTENTE_BENEFICIAIRE"]
        if view.snapshot.orientation_published_version is not None and view.snapshot.orientation_feedback is None:
            st.write("**Mes idées et premières directions**")
            _button("Relire", "b_orientation", key="validate_orientation", primary=True)
        if not pending and not (view.snapshot.orientation_published_version is not None and view.snapshot.orientation_feedback is None):
            st.success("Aucun élément n'attend votre validation.")
        for phase in pending:
            st.write(f"**{FRIENDLY_PHASE.get(phase, 'Élément à relire')}**")
            _button("Relire", beneficiary_phase_page(phase), key=f"validate_{phase}", primary=True)
    else:
        st.title("Terminé")
        done = [phase for phase, state in view.snapshot.phase_states if state in {"VALIDEE", "FIGEE_CLOTURE"}]
        if not done:
            st.info("Les éléments terminés apparaîtront ici au fur et à mesure.")
        for phase in done:
            st.markdown(f"✓ **{FRIENDLY_PHASE.get(phase, 'Étape terminée')}**")
        for task in view.snapshot.tasks:
            if task.state == "CLOTUREE":
                st.markdown(f"✓ **Vérification : {task.goal}**")
    _button("Revenir à l'accueil", "b_home", key=f"cat_home_{category}")


def _read_only_banner(view: BeneficiaryHomeView, phase_no: int) -> None:
    import streamlit as st
    state = _phase_states(view).get(phase_no)
    st.markdown(
        f"<div class='clarte-readonly'><strong>Lecture de mon résultat</strong><span>{_beneficiary_state_label(state)}</span><small>Vous pouvez revenir sur cette étape à tout moment. Le contenu partagé est en lecture seule ; une action séparée apparaît seulement lorsqu'une confirmation ou une saisie vous est demandée.</small></div>",
        unsafe_allow_html=True,
    )


def render_phase(ctx, view: BeneficiaryHomeView, phase_no: int) -> None:
    import streamlit as st
    title = FRIENDLY_PHASE.get(phase_no, "Mon bilan")
    st.title(title)
    _read_only_banner(view, phase_no)

    if phase_no == 0:
        st.caption("Voici le parcours que votre accompagnateur a relu avec vous et partagé après votre séance.")
        st.info("Les études sans diplôme, les formations et l’apprentissage personnel peuvent aussi faire apparaître des savoirs utiles. Le niveau discuté décrit une expérience précise ; il ne classe pas votre personne.")
        st.markdown("### Mon parcours professionnel enrichi")
        if view.snapshot.career_details:
            for card in view.snapshot.career_details:
                label = {"EMPLOI": "Expérience professionnelle", "ETUDE": "Études",
                    "FORMATION": "Formation", "AUTOFORMATION": "Apprentissage personnel", "AUTRE": "Autre élément"}.get(card.item_type, card.item_type.replace("_", " ").title())
                with st.expander(f"{label} — {card.title}", expanded=False):
                    if card.organization:
                        st.caption(card.organization)
                    period = " — ".join(value for value in (card.start_date, card.end_date) if value)
                    if period:
                        st.caption(period)
                    for detail_label, value in card.details:
                        st.markdown(f"**{detail_label}**")
                        st.write(value)
        else:
            st.info("Votre accompagnateur partagera ici le parcours après l’avoir relu avec vous en séance.")

        state = _phase_states(view).get(0)
        shared_version = view.snapshot.career_phase_version
        feedback_version = view.snapshot.career_feedback_version
        feedback = view.snapshot.career_feedback
        feedback_is_current = (
            feedback_version is not None and shared_version is not None and (
                (feedback == "CONFIRME" and shared_version == feedback_version)
                or (feedback == "CORRECTION_DEMANDEE" and shared_version == feedback_version + 1)
            )
        )
        if feedback_is_current and feedback == "CONFIRME":
            st.success("Votre confirmation est enregistrée pour cette version. Si vous constatez ensuite une erreur, contactez votre accompagnateur pour demander une nouvelle version.")
        elif feedback_is_current and feedback == "CORRECTION_DEMANDEE":
            st.warning("Votre demande de correction a été transmise à votre accompagnateur.")
            if view.snapshot.career_feedback_comment:
                st.markdown("**Votre remarque**")
                st.write(view.snapshot.career_feedback_comment)
        elif state == "VALIDEE" and shared_version is not None:
            st.markdown("#### Votre retour sur ce parcours")
            st.caption("Une seule réponse est possible pour cette version. Relisez les éléments; si vous confirmez, une correction ultérieure devra être demandée à votre accompagnateur.")
            with st.form(f"career_phase0_feedback_{view.snapshot.case_id}_{shared_version}"):
                choice = st.radio("Que souhaitez-vous faire ?", ("CONFIRME", "CORRECTION_DEMANDEE"),
                    format_func=lambda value: "Je confirme que ce parcours correspond à nos échanges" if value == "CONFIRME" else "Je demande une correction", horizontal=False)
                comment = st.text_area("Si vous demandez une correction, indiquez ce qui doit être modifié", max_chars=1000,
                    help="Vous pouvez préciser une expérience à compléter, une information inexacte ou un élément manquant.")
                confirm_send = st.checkbox("J’ai relu cette version et confirme l’envoi de mon retour.")
                submitted = st.form_submit_button("Envoyer mon retour", type="primary", use_container_width=True, disabled=not confirm_send)
            if submitted:
                try:
                    respond_to_career_phase(ctx, view.snapshot.case_id, version=shared_version,
                        decision=choice, comment=comment)
                    st.success("Votre retour a été transmis à votre accompagnateur.")
                    st.rerun()
                except (ValueError, CareerFeedbackConflict) as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("Votre réponse n’a pas pu être enregistrée. Actualisez la page et réessayez.")

        st.markdown("#### Conserver et réutiliser ce travail")
        st.info("Les fichiers téléchargeables seront disponibles depuis Mes documents lorsque la version finale aura été remise dans l'espace partagé. En attendant, vous pouvez relire ce contenu à l'écran avec votre accompagnateur.")

    elif phase_no == 1:
        st.caption("Résultat partagé : les pistes que vous avez réellement accepté d'explorer. Elles ne sont pas des recommandations automatiques.")
        if view.snapshot.ideas:
            for _idea_id, wording, origin in view.snapshot.ideas:
                origin_label = "Idée exprimée" if origin != "IA" else "Hypothèse ajoutée après discussion"
                st.markdown(f"<div class='clarte-card'><strong>{escape(wording)}</strong><span>{escape(origin_label)}</span><small>Une piste peut être écartée ou reformulée sans que cela constitue une mauvaise réponse.</small></div>", unsafe_allow_html=True)
        else:
            st.info("Aucune piste n'est encore prête à relire.")
        st.caption("Si une piste ne correspond pas à ce que vous avez exprimé, indiquez-le à votre accompagnateur pendant la séance.")

    elif phase_no == 2:
        st.caption("Résultat partagé : les métiers de référence retenus pour l'étude approfondie.")
        if view.snapshot.job_targets:
            for _job_id, label, code in view.snapshot.job_targets:
                st.markdown(f"<div class='clarte-card'><strong>{escape(label)}</strong><span>Métier étudié</span><small>Référence ROME : {escape(code)}</small></div>", unsafe_allow_html=True)
                interest = rome_interest_context(code)
                if interest:
                    st.caption(f"Repère d’intérêt de la fiche ROME : RIASEC {interest['riasec_code']} · {interest['source_label']}")
                    st.caption("À mettre en regard de vos intérêts PIP avec votre accompagnateur. Ce repère ne dit pas si vous avez les compétences ou l’aptitude pour exercer ce métier.")
        else:
            st.info("Les métiers à étudier apparaîtront ici.")
        render_research_resources(groups=(RESOURCE_GROUPS[0][0],))
        st.caption("Les métiers étudiés se confirment avec votre accompagnateur. Signalez-lui toute correction avant la poursuite de l'analyse.")

    elif phase_no == 3:
        st.caption("Résultat partagé : une synthèse pédagogique de ce que votre parcours permet déjà d'étayer face aux métiers étudiés.")
        st.info("Vos savoirs peuvent venir de vos expériences, de vos études même sans diplôme, de formations ou d’apprentissages personnels. Un diplôme n’est bloquant que si une source officielle confirme qu’il est obligatoire pour exercer le métier.")
        counts = dict(view.snapshot.matching_counts)
        st.markdown(
            f"<div class='clarte-card'><strong>Ce qui est déjà clair</strong><span>{counts.get('ACQUIS_PAR_PARCOURS', 0)} élément(s) étayé(s)</span><small>À préciser ensemble : {counts.get('A_CONFIRMER', 0)} · À vérifier/développer : {counts.get('NON_DOCUMENTE', 0) + counts.get('A_DEVELOPPER', 0)}</small></div>",
            unsafe_allow_html=True,
        )
        details = getattr(view.snapshot, "matching_details", ())
        if details:
            st.markdown("#### Les savoirs rapprochés de votre parcours")
            for item in details:
                st.markdown(f"**{item.job_code} — {item.job_label}**")
                level_text = ({1: "Niveau 1 — Pratique encadrée / contribution",
                               2: "Niveau 2 — Maîtrise autonome",
                               3: "Niveau 3 — Pilotage, expertise ou transmission"}
                              .get(item.exercise_level, "Niveau à préciser"))
                st.markdown(f"<div class='clarte-card'><strong>{escape(item.item_label)}</strong><span>{escape(item.status.replace('_', ' ').title())}</span><small>{escape(level_text)} · {escape('Étayé par : ' + ', '.join(item.evidence_titles) if item.evidence_titles else 'Aucun élément du parcours relié à ce stade')}</small></div>", unsafe_allow_html=True)
                if item.rationale:
                    st.caption(item.rationale)
        else:
            st.info("Aucun rapprochement n’a encore été validé en séance. Cette vue est en lecture seule ; la sélection et le rapprochement sont conduits par l’accompagnateur avec vous.")

    elif phase_no == 4:
        st.caption("Résultat partagé : les points encore incertains et la manière dont ils ont été traités avec votre accompagnateur.")
        st.info("Les points à préciser apparaîtront ici lorsqu'ils auront été consignés pour votre dossier. Une question hors séance sera proposée dans Mes actions uniquement si elle est utile à votre projet.")
        st.info("Si une réponse vous est demandée hors séance, elle apparaîtra dans Mes actions, pas dans cette page de lecture.")

    elif phase_no == 5:
        st.caption("Résultat partagé : ce qui est établi, ce qui reste à vérifier et les retours de terrain utiles au projet.")
        st.caption("Les exigences obligatoires sont vérifiées séparément des diplômes seulement souhaités par certains employeurs. Une formation n’est envisagée que pour répondre à une obligation vérifiée ou à un besoin que vous souhaitez travailler.")
        tasks = [t for t in view.snapshot.tasks if t.state in {"PUBLIEE", "EN_COURS", "SOUMISE", "A_DEBRIEFER"}]
        if tasks:
            for task in tasks:
                st.markdown(f"<div class='clarte-card'><strong>{escape(task.goal)}</strong><span>{escape(task.state.replace('_',' ').title())}</span><small>Cette vérification complète le travail commun ; elle ne remplace pas la séance.</small></div>", unsafe_allow_html=True)
            _button("Voir mes actions", "b_actions", key="phase5_actions", primary=True)
        else:
            st.info("Aucune vérification ne vous est demandée pour le moment.")
        render_research_resources(groups=(RESOURCE_GROUPS[1][0],))

    elif phase_no == 6:
        st.caption("Résultat partagé : la comparaison qualitative des pistes, sans note ni classement automatique.")
        if view.snapshot.comparison_cells:
            by_criterion: dict[str, list[str]] = {}
            labels = {jid: label for jid, label, _code in view.snapshot.job_targets}
            for job_id, criterion, content in view.snapshot.comparison_cells:
                by_criterion.setdefault(criterion, []).append(f"**{labels.get(job_id, 'Piste')}** — {content}")
            for criterion, entries in by_criterion.items():
                st.markdown(f"#### {criterion}")
                for entry in entries:
                    st.markdown(entry)
        else:
            st.info("La comparaison apparaîtra ici lorsque les vérifications seront suffisantes.")

    elif phase_no == 7:
        st.caption("Résultat partagé : le projet que vous retenez et les conditions qui rendent ce choix réaliste.")
        if view.snapshot.project_decision:
            job_id, wording = view.snapshot.project_decision
            labels = {jid: label for jid, label, _code in view.snapshot.job_targets}
            st.markdown(f"<div class='clarte-card'><strong>{escape(labels.get(job_id, 'Projet'))}</strong><span>Projet prioritaire retenu</span><small>{escape(wording)}</small></div>", unsafe_allow_html=True)
        if view.snapshot.project_alternative:
            job_id, wording = view.snapshot.project_alternative
            labels = {jid: label for jid, label, _code in view.snapshot.job_targets}
            st.markdown(f"<div class='clarte-card'><strong>Alternative : {escape(labels.get(job_id, 'Projet'))}</strong><span>Option conservée</span><small>{escape(wording)}</small></div>", unsafe_allow_html=True)
        else:
            st.info("Votre projet prioritaire sera formulé ici avec vos propres raisons.")
        st.caption("Le projet retenu reprend votre décision formulée en séance. Indiquez à votre accompagnateur si cette formulation doit être reprise.")

    elif phase_no == 8:
        st.caption("Résultat partagé : votre feuille de route construite avec votre accompagnateur.")
        plan = read_action_plan(ctx, view.snapshot.case_id)
        if plan["items"]:
            for i, item in enumerate(plan["items"], start=1):
                detail = ('Moyens : ' + item['means'] if item['means'] else '') + (' · ' if item['means'] and item['expected'] else '') + ('Résultat attendu : ' + item['expected'] if item['expected'] else '')
                st.markdown(f"<div class='clarte-card'><strong>{i}. {escape(item['action'])}</strong><span>{escape(item['due'] or 'Repère à préciser')}</span><small>{escape(detail)}</small></div>", unsafe_allow_html=True)
            if plan["beneficiary_response"]:
                st.success("Votre réponse à cette version du plan a été transmise.")
            else:
                st.info("Votre réponse sera enregistrée une seule fois pour cette version. Si vous demandez un ajustement, votre accompagnateur reprendra le plan avec vous.")
                with st.form(f"beneficiary_action_plan_{plan['plan_id']}"):
                    adjustment = st.text_area("Si vous souhaitez un ajustement, dites lequel", max_chars=2000,
                                              placeholder="Facultatif si vous confirmez le plan.")
                    confirm_send = st.checkbox("J’ai relu cette version et confirme l’envoi de ma réponse.")
                    confirm = st.form_submit_button("Confirmer le plan", type="primary", disabled=not confirm_send)
                    request = st.form_submit_button("Demander un ajustement", disabled=not confirm_send)
                if confirm or request:
                    try:
                        respond_to_action_plan(ctx, view.snapshot.case_id, plan_id=plan["plan_id"],
                            response="CONFIRME" if confirm else "AJUSTEMENT_DEMANDE", comment=adjustment)
                        st.success("Votre réponse a été transmise à votre accompagnateur.")
                        st.rerun()
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
        else:
            if plan.get("out_of_date"):
                st.info("Votre projet a été réexaminé avec votre accompagnateur. Le nouveau plan d’action sera partagé ici après sa mise à jour.")
            else:
                st.info("Votre plan d'action sera affiché ici lorsqu'il sera préparé avec votre accompagnateur.")
        render_research_resources(groups=(RESOURCE_GROUPS[2][0],))

    elif phase_no == 9:
        st.caption("Résultat partagé : vos résultats détaillés, distincts de la synthèse finale.")
        closing = read_conclusion(ctx, view.snapshot.case_id)
        results = closing["results"]
        if not results:
            st.info("Votre accompagnateur prépare encore cette restitution. Vous serez informé lorsqu'elle sera prête.")
        else:
            st.caption(f"Version {results['version']} · {results['state'].replace('_', ' ').title()}")
            labels = {"parcours": "Parcours et éléments déterminants", "savoirs": "Savoirs et compétences mobilisables",
                      "projet": "Projet retenu et raisons", "conditions": "Conditions de réalisation",
                      "vigilances": "Points de vigilance et vérifications", "formations": "Formations ou certifications envisagées",
                      "diploma_status": "Diplôme ou titre obligatoire, le cas échéant", "diploma_source": "Source officielle et date"}
            for key, label in labels.items():
                value = results["content"].get(key, "")
                if value:
                    st.markdown(f"**{label}**")
                    st.write(value)
            if results["state"] == "PUBLIE_POUR_RELECTURE":
                st.info("Vous pouvez confirmer cette version ou demander une correction. Votre réponse sera transmise à l’accompagnateur et enregistrée pour cette version.")
                with st.form(f"beneficiary_results_{results['id']}"):
                    comment = st.text_area("Si vous demandez une correction, précisez laquelle", max_chars=2000)
                    confirm_send = st.checkbox("J’ai relu cette version et confirme l’envoi de ma réponse.")
                    confirm = st.form_submit_button("Confirmer la relecture", type="primary", disabled=not confirm_send)
                    correct = st.form_submit_button("Demander une correction", disabled=not confirm_send)
                if confirm or correct:
                    try:
                        respond_to_conclusion(ctx, view.snapshot.case_id, artifact_version_id=results["id"],
                            object_type="RESULTS", response="CONFIRME" if confirm else "CORRECTION_DEMANDEE", comment=comment)
                        st.success("Votre réponse a été transmise à votre accompagnateur.")
                        st.rerun()
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
            elif results["state"] == "CONFIRMEE":
                st.success("Vous avez confirmé la relecture de cette version.")

    elif phase_no == 10:
        st.caption("Résultat partagé : votre synthèse finale, relue avec vous avant finalisation.")
        closing = read_conclusion(ctx, view.snapshot.case_id)
        synthesis = closing["synthesis"]
        if not synthesis:
            st.info("La synthèse finale sera affichée ici après la relecture des résultats détaillés.")
        else:
            st.caption(f"Version {synthesis['version']} · {synthesis['state'].replace('_', ' ').title()}")
            labels = {"objectif": "Objectif du bilan", "projet": "Projet professionnel retenu",
                      "conditions": "Conditions et moyens de réalisation", "plan": "Plan d'action convenu",
                      "suite": "Perspectives et points à reprendre"}
            for key, label in labels.items():
                value = synthesis["content"].get(key, "")
                if value:
                    st.markdown(f"**{label}**")
                    st.write(value)
            if synthesis["state"] == "PUBLIE_POUR_RELECTURE":
                st.info("Vous pouvez confirmer cette version ou demander une correction. Votre réponse sera transmise à l’accompagnateur et enregistrée pour cette version.")
                with st.form(f"beneficiary_synthesis_{synthesis['id']}"):
                    comment = st.text_area("Si vous demandez une correction, précisez laquelle", max_chars=2000)
                    confirm_send = st.checkbox("J’ai relu cette version et confirme l’envoi de ma réponse.")
                    confirm = st.form_submit_button("Confirmer la relecture", type="primary", disabled=not confirm_send)
                    correct = st.form_submit_button("Demander une correction", disabled=not confirm_send)
                if confirm or correct:
                    try:
                        respond_to_conclusion(ctx, view.snapshot.case_id, artifact_version_id=synthesis["id"],
                            object_type="SYNTHESIS", response="CONFIRME" if confirm else "CORRECTION_DEMANDEE", comment=comment)
                        st.success("Votre réponse a été transmise à votre accompagnateur.")
                        st.rerun()
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
            elif synthesis["state"] == "FINALISEE":
                st.success("La version finale a été établie après votre relecture.")

    else:
        st.caption("Résultat partagé : ce qui vous est remis et les repères de suite après le bilan.")
        st.markdown("<div class='clarte-card'><strong>Je repars avec</strong><span>Mon plan d'action · Mes résultats détaillés · Ma synthèse</span><small>Clarté360 prévoit un point de suivi à 6 mois dans son parcours d'accompagnement ; ce délai n'est pas présenté comme une obligation légale.</small></div>", unsafe_allow_html=True)
        closing = read_conclusion(ctx, view.snapshot.case_id)
        if closing["closed"]:
            st.success("Votre parcours est clôturé.")
        if closing["followup"]:
            st.info(f"Un point de suivi est prévu autour du {closing['followup']['date']}.")
            due = date.fromisoformat(closing["followup"]["date"])
            if closing["followup"]["status"] == "PLANIFIE" and date.today() < due:
                st.caption("Vous pourrez transmettre votre point de situation à partir de cette date.")
            elif closing["followup"]["status"] == "PLANIFIE":
                st.warning("Le point transmis sera définitif dans votre espace. Relisez votre message avant l’envoi; pour un complément, contactez votre accompagnateur.")
                with st.form("beneficiary_followup_form"):
                    followup = st.text_area("Où en êtes-vous aujourd'hui ? Quelles avancées ou difficultés souhaitez-vous partager ?", max_chars=8000, height=140)
                    confirm_send = st.checkbox("J’ai relu mon point de situation et confirme son envoi.")
                    submit = st.form_submit_button("Envoyer définitivement mon point de suivi", type="primary", disabled=not confirm_send)
                if submit:
                    try:
                        submit_followup_response(ctx, view.snapshot.case_id, content=followup)
                        st.success("Votre point de suivi a été transmis.")
                        st.rerun()
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
        _button("Voir mes documents", "b_documents", key="phase11_docs", primary=True)

    nav = st.columns(2)
    with nav[0]:
        _button("Retour à mon parcours", "b_journey", key=f"phase_journey_{phase_no}")
    with nav[1]:
        _button("Retour à l'accueil", "b_home", key=f"phase_home_{phase_no}")


def render_intersession(ctx, case_id: str) -> None:
    import streamlit as st
    st.title("Mon action hors séance")
    try:
        tasks = read_intersession_tasks(ctx, case_id)
    except Exception:
        st.error("Cette action n’est pas accessible dans la session actuelle.")
        return
    visible = [t for t in tasks if t["state"] in {"PUBLIEE", "EN_COURS", "SOUMISE", "A_DEBRIEFER"}]
    selected_id = st.session_state.get("intersession_task_id")
    task = next((t for t in visible if t["task_id"] == selected_id), None) or (visible[0] if visible else None)
    if task is None:
        st.info("Aucune action hors séance n'est active pour le moment.")
        _button("Revenir à mes actions", "b_actions", key="is_actions_empty")
        return
    st.markdown(f"**{task['task_type_label']}**")
    if task.get("job_target_label"):
        st.caption(f"Métier étudié : {task.get('job_target_code')} — {task['job_target_label']}")
    st.info(task["goal"])
    group_by_type = {
        "ENQUETE_METIER": (RESOURCE_GROUPS[0][0],),
        "OFFRES_EMPLOI": (RESOURCE_GROUPS[0][0],),
        "TERRITOIRE": (RESOURCE_GROUPS[1][0],),
        "CONDITION_ACCES": (RESOURCE_GROUPS[0][0], RESOURCE_GROUPS[2][0]),
        "FORMATION": (RESOURCE_GROUPS[2][0],),
        "AUTRE": tuple(group for group, _resources in RESOURCE_GROUPS),
    }
    render_research_resources(groups=group_by_type.get(task["task_type"], tuple(group for group, _ in RESOURCE_GROUPS)))
    response = task.get("response") or {}
    if task["state"] in {"SOUMISE", "A_DEBRIEFER"}:
        st.success("Votre retour a été transmis à votre accompagnateur.")
        st.markdown(f"**Source :** {response.get('source', '—')} · **Date :** {response.get('consulted_on', '—')}")
        st.markdown("**Ce que j’ai appris**")
        st.write(response.get("learned", "—"))
        st.markdown("**Effet sur mon projet**")
        st.write(response.get("project_impact", "—"))
    else:
        if task["state"] == "EN_COURS" and response.get("response_state") == "BROUILLON":
            st.caption("Votre brouillon enregistré est repris ci-dessous.")
        with st.form(f"intersession_response_{task['task_id']}"):
            source = st.text_input("1. Source consultée", value=response.get("source", ""), max_chars=2400)
            consulted_on = st.text_input("2. Date de consultation", value=response.get("consulted_on", ""), max_chars=10, placeholder="AAAA-MM-JJ")
            learned = st.text_area("3. Ce que j’ai appris", value=response.get("learned", ""), max_chars=2400, height=110)
            project_impact = st.text_area("4. Ce que cela confirme, modifie ou laisse à vérifier dans mon projet", value=response.get("project_impact", ""), max_chars=2400, height=100)
            save = st.form_submit_button("Enregistrer et reprendre plus tard", use_container_width=True)
            confirm_send = st.checkbox("J’ai relu mon retour et confirme qu’il peut être envoyé à mon accompagnateur.")
            submit = st.form_submit_button("Envoyer mon retour pour le débrief", type="primary", use_container_width=True, disabled=not confirm_send)
        if save or submit:
            try:
                if save:
                    save_intersession_draft(ctx, case_id, task["task_id"], source=source,
                        consulted_on=consulted_on, learned=learned, project_impact=project_impact)
                    st.success("Brouillon enregistré. Vous pourrez reprendre cette action plus tard.")
                else:
                    submit_intersession_response(ctx, case_id, task["task_id"], source=source,
                        consulted_on=consulted_on, learned=learned, project_impact=project_impact)
                    st.success("Votre retour a été transmis à votre accompagnateur pour le débrief en séance.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("Votre retour n’a pas pu être enregistré. Votre saisie reste affichée dans cette fenêtre.")
    _button("Revenir à mes actions", "b_actions", key="is_actions")


def render_beneficiary_app(ctx, bootstrap) -> None:
    import streamlit as st
    view = build_beneficiary_home(bootstrap.case_id)
    render_header(ctx, view)
    render_nav()

    page = st.session_state.get("navigation_page", "home")
    if page in {"home", "dashboard"}:
        page = "b_home"
        st.session_state["navigation_page"] = page

    if page == "b_home":
        render_home(ctx, view)
    elif page == "b_journey":
        render_journey(view)
    elif page == "b_orientation":
        render_beneficiary_orientation(ctx, bootstrap.case_id)
    elif page == "b_preparation":
        render_beneficiary_preparation(ctx, bootstrap.case_id)
    elif page == "b_actions":
        render_actions(view)
    elif page == "b_documents":
        render_documents(ctx, bootstrap.case_id, view)
    elif page == "b_read":
        render_category(view, "read")
    elif page == "b_do":
        render_category(view, "do")
    elif page == "b_validate":
        render_category(view, "validate")
    elif page == "b_done":
        render_category(view, "done")
    elif page == "b_intersession":
        render_intersession(ctx, bootstrap.case_id)
    elif page.startswith("b_phase_"):
        try:
            phase_no = int(page.rsplit("_", 1)[1])
        except ValueError:
            phase_no = 0
        render_phase(ctx, view, phase_no)
    else:
        st.session_state["navigation_page"] = "b_home"
        st.rerun()
