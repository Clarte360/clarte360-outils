from __future__ import annotations

from datetime import datetime
from html import escape

from clarte360_cp.application.dashboard import AccompanistDashboardView, build_accompanist_dashboard
from clarte360_cp.framework.navigation import set_page
from clarte360_cp.ui.spec import PHASE_BY_NO, PHASE_SPECS, SOURCE_CARDS, choose_next_action, phase_page
from clarte360_cp.ui.live_sync import render_live_sync_status
from clarte360_cp.ui.orientation import render_ideas, render_reperes, render_directions
from clarte360_cp.ui.preparation import render_questionnaire_builder, render_joint_review, render_cav3_source_summary
from clarte360_cp.ui.rome_workshop import (
    render_career_enrichment, render_rome_target_selection, render_rome_matching,
    render_rome_clarification, render_rome_investigations,
)
from clarte360_cp.application.preparation import read_preparation
from clarte360_cp.application.go23 import (
    CRITERIA, read_go23, save_comparison, record_project_decision, publish_project_decision,
)
from clarte360_cp.application.go24 import read_action_plan, save_action_plan
from clarte360_cp.application.conclusion import (
    RESULT_FIELDS, SYNTHESIS_FIELDS, close_bilan, finalize_synthesis,
    read_conclusion, save_followup_plan, save_results, save_synthesis,
)
from clarte360_cp.application.phase_progress import phase_readiness, validate_phase
from clarte360_cp.domain.phases import PHASE_NEXT, phase_display_number
from clarte360_cp.application.career_feedback import read_career_phase_feedback


def _gda_engine():
    from clarte360_cp.repositories.db import build_engine
    return build_engine()


def _render_gda_document_workspace(ctx, case_id: str, gda):
    import streamlit as st
    from clarte360_cp.repositories.db import session_factory
    from clarte360_cp.repositories.gda_documents import (
        list_linked_gda_documents, link_document_to_purpose, save_external_reference,
    )
    with st.spinner("Lecture de l’inventaire documentaire autorisé…"):
        external = gda.list_sources()
    engine = _gda_engine()
    with session_factory(engine)() as session:
        for item in external:
            save_external_reference(session, ctx, case_id, item)
        visible_refs = {str(item["source_ref"]) for item in external}
        records = [(doc, link) for doc, link in list_linked_gda_documents(session, case_id)
                   if doc.source_ref in visible_refs]
    if external:
        purposes = {
            "APS_OBJECTIF": "APS — objectif professionnel",
            "BOUSSOLE_VALEURS": "Boussole des valeurs",
            "MOTEURS_PRO": "Moteurs professionnels",
            "PREFERENCES_PRO": "Préférences professionnelles",
            "IPIP_REPORT": "Rapport IPIP",
            "PIP_REPORT": "Rapport PIP — accompagnement",
            "CV_SOURCE": "CV source",
            "AUTRE_PARCOURS": "Autre document de parcours",
        }
        with st.expander(f"Documents partagés · {len(external)} référence(s)", expanded=True):
            for document, link in records:
                purpose_label = purposes.get(link.purpose, link.purpose) if link else "À relier"
                depositor = {
                    "ADMINISTRATEUR": "Administrateur",
                    "ACCOMPAGNATEUR": "Intervenant",
                    "BENEFICIAIRE": "Bénéficiaire",
                }.get(document.source_created_by_role or "", "Déposant non renseigné")
                st.write(f"**{document.display_name}** · {purpose_label} · version {document.source_version}")
                st.caption(f"Déposé par : {depositor}")
                if st.checkbox("Informations techniques du document", key=f"gda_doc_meta_{document.source_ref}"):
                    st.caption(f"Référence : …{document.source_ref[-8:]} · déposant …{(document.source_created_by_ref or '')[-6:]} · {document.size_bytes} octets · {document.mime_type} · SHA-256 {document.sha256[:12]}…")
            if records:
                options = {f"{doc.display_name} · …{doc.source_ref[-8:]} · v{doc.source_version}": doc for doc, _ in records}
                with st.form("gda_cp_manual_link_form"):
                    selected = st.selectbox("Document à relier", list(options))
                    purpose = st.selectbox("Besoin du bilan", list(purposes), format_func=purposes.get)
                    link = st.form_submit_button("Enregistrer le lien manuel", type="primary")
                if link:
                    try:
                        with session_factory(engine)() as session:
                            link_document_to_purpose(session, ctx, case_id, options[selected].external_document_id, purpose)
                        st.success("Lien enregistré avec l’identité de l’accompagnateur et son historique.")
                        st.rerun()
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
        if "CV_SOURCE" not in {link.purpose for _, link in records if link}:
            st.warning("Le CV source doit être choisi dans l’espace partagé puis relié manuellement avant l’étude détaillée du parcours.")
    else:
        st.info("Aucun document publié n’est visible pour cette action. Déposez le document manquant, puis reliez-le explicitement au besoin du bilan.")
    if ctx.has_scope("CP_SOURCE_MANUAL_IMPORT"):
        upload = st.file_uploader("Déposer un document dans l’espace partagé du dossier", key="gda_cp_source_upload")
        st.caption("Le fichier est enregistré par GDA et reste non associé jusqu’au lien manuel. C&P ne le copie pas et ne lance aucune reconnaissance automatique.")
        if st.button("Déposer dans Gestion des Actions", key="gda_cp_source_upload_btn", disabled=upload is None):
            try:
                item = gda.put_unlinked(upload.name, upload.getvalue(), mime_type=upload.type)
                with session_factory(engine)() as session:
                    save_external_reference(session, ctx, case_id, item)
                st.success(f"Document déposé dans l’espace partagé · référence …{item['source_ref'][-8:]}. Il reste à relier manuellement.")
                st.rerun()
            except Exception as exc:
                from clarte360_cp.connectors.gda_documents import GDAError
                if isinstance(exc, (GDAError, ValueError, PermissionError)):
                    st.error(str(exc))
                else:
                    st.error("Le dépôt n’a pas été confirmé par Gestion des Actions. Vérifiez la liste avant de réessayer.")
    if records:
        labels = {f"{doc.display_name} · v{doc.source_version} · …{doc.source_ref[-8:]}" : doc for doc, _ in records}
        chosen = st.selectbox("Ouvrir un document partagé", list(labels), key="gda_cp_open_select")
        if st.button("Ouvrir depuis Gestion des Actions", key="gda_cp_open_btn"):
            try:
                metadata, content = gda.get_source(labels[chosen].source_ref)
                st.download_button("Télécharger le document", content,
                    file_name=metadata.get("display_name") or "document", mime=metadata["mime_type"],
                    key=f"gda_cp_download_{metadata['source_ref']}")
            except Exception as exc:
                st.error(str(exc))
    return {link.purpose for _, link in records if link}


def _render_cv_enrichment_after_cav3(ctx, case_id: str) -> None:
    """GO22 order gate: CV analysis is available only after a current C-AV3 run."""
    import streamlit as st
    from clarte360_cp.application.preparation import cav3_analysis_history
    from clarte360_cp.application.cv_enrichment import record_cv_ai_analysis
    from clarte360_cp.connectors.cav3_ai import Cav3AIError, Cav3AISettings
    from clarte360_cp.connectors.cv_enrichment_ai import analyze_cv_text, extract_cv_text
    from clarte360_cp.connectors.gda_documents import GDAError, GDADocumentClient, load_gda_settings
    from clarte360_cp.repositories.db import session_factory
    from clarte360_cp.repositories.gda_documents import list_linked_gda_documents, save_external_reference

    st.markdown("#### Préparer les cartes du parcours depuis le CV")
    try:
        history = cav3_analysis_history(ctx, case_id)
        current_cav3 = next((row for row in reversed(history) if row.get("current")), None)
    except Exception:
        current_cav3 = None
    if current_cav3 is None:
        st.info("Cette étape s’ouvre après la préparation de questions d’entretien à partir des réponses envoyées ou relues en séance. Si les réponses ont changé, reprenez cette préparation.")
        return

    settings = load_gda_settings(st.secrets)
    token = str(st.session_state.get("gda_launch_token", ""))
    if not settings.configured or not token or not ctx.has_scope("CP_SOURCE_GDA_READ"):
        st.info("La référence CV doit être reliée dans l’espace partagé GDA avant son analyse.")
        return
    gda = GDADocumentClient(settings, token)
    try:
        external = gda.list_sources()
        with session_factory(_gda_engine())() as session:
            for item in external:
                save_external_reference(session, ctx, case_id, item)
            visible_refs = {str(item["source_ref"]) for item in external}
            linked = [(doc, link) for doc, link in list_linked_gda_documents(session, case_id)
                      if link and link.purpose == "CV_SOURCE" and doc.source_ref in visible_refs]
    except (GDAError, PermissionError, ValueError) as exc:
        st.warning(str(exc))
        return
    if not linked:
        st.info("Dans Sources et CV, choisissez un document de l’espace partagé et reliez-le manuellement au besoin « CV source ».")
        return

    st.caption("Le texte du CV sera envoyé à l’API IA partagée (store=false). Le nom et les coordonnées/adresses usuelles en tête sont retirés ; aucune carte n’est créée avant votre action.")
    labels = {f"{doc.display_name} · v{doc.source_version} · …{doc.source_ref[-8:]}": doc for doc, _ in linked}
    selected = st.selectbox("CV relié au besoin CV source", list(labels), key=f"cp_cv_select_{case_id}")
    document = labels[selected]
    key = f"cp_cv_analysis_{case_id}_{document.source_ref}_{document.source_version}"
    consented = st.checkbox("J’ai expliqué cet envoi au bénéficiaire et il accepte que le texte du CV soit analysé par l’IA pour préparer l’entretien.", key=f"cp_cv_ai_consent_{case_id}_{document.source_ref}")
    if st.button("Analyser ce CV et préparer des questions", key=f"cp_cv_analyze_{case_id}", type="primary", disabled=not consented):
        try:
            ai_settings = Cav3AISettings.from_streamlit_secrets()
            with st.spinner("Lecture temporaire du CV et préparation des questions…"):
                metadata, content = gda.get_source(document.source_ref)
                cv_text = extract_cv_text(content, metadata.get("display_name", document.display_name),
                                          metadata.get("mime_type", document.mime_type))
                result = analyze_cv_text(cv_text, ai_settings, source_refs=[document.source_ref])
            record_cv_ai_analysis(ctx, case_id, document.source_ref, document.source_version,
                                  result["metadata"], database_url=str(_gda_engine().url))
            st.session_state[key] = result
            st.success(f"{len(result['parcours'])} proposition(s) à vérifier en séance.")
        except Exception as exc:
            st.error(str(exc) if isinstance(exc, Cav3AIError) else "L’analyse du CV n’a pas abouti. Vérifiez la référence, le format et la configuration de l’API.")
    result = st.session_state.get(key)
    if not result:
        return
    if result.get("incertitudes"):
        st.warning("À vérifier : " + " · ".join(result["incertitudes"]))
    for index, item in enumerate(result.get("parcours", [])):
        title = str(item.get("intitule") or "Élément à préciser")
        with st.expander(f"{index + 1}. {title} · {item.get('debut') or 'date à préciser'} — {item.get('fin') or 'date à préciser'}", expanded=index == 0):
            st.write(item.get("activites") or "Activités à préciser.")
            if item.get("structure"):
                st.caption("Structure proposée : " + str(item["structure"]))
            for label, field in (("Résultats", "realisations"), ("Autonomie", "autonomie"), ("Outils", "outils"), ("Savoirs évoqués", "savoirs"), ("Extrait du CV", "preuve_cv")):
                if item.get(field):
                    st.markdown(f"**{label} :** {item[field]}")
            if item.get("questions_seance"):
                st.markdown("**Questions à poser ensemble**")
                for question in item["questions_seance"]:
                    st.markdown(f"- {question}")
            if st.button("Ajouter comme carte à confirmer", key=f"cp_cv_add_{case_id}_{document.source_ref}_{index}"):
                try:
                    add_session_experience(ctx, case_id, title=title[:240], kind=item["nature"],
                        organization=item["structure"][:240], period_start=item["debut"][:20], period_end=item["fin"][:20],
                        context=item["contexte"][:2400], activities=item["activites"][:2400], autonomy=item["autonomie"][:1200],
                        achievements=item["realisations"][:2400], tools=item["outils"][:1200], knowledge=item["savoirs"][:1600],
                        source_ref=document.source_ref, source_span_ref=f"CV:{document.source_ref}:{index}")
                    st.success("Carte ajoutée avec sa référence documentaire et le statut « à confirmer ». Aucun niveau n’a été déduit. Discutez-en avec le bénéficiaire à l’étape du parcours professionnel.")
                    st.rerun()
                except Exception:
                    st.error("La carte n’a pas pu être ajoutée. Reprenez les faits avec le bénéficiaire dans l’étape du parcours professionnel.")
    if result.get("points_a_verifier"):
        with st.expander("Questions transversales pour l’entretien"):
            for question in result["points_a_verifier"]:
                st.markdown(f"- {question}")


def _render_final_deliverable(ctx, case_id: str, kind: str, version: str | int,
                              document_id: str, display_name: str, content: bytes,
                              *, word_content: bytes | None = None, word_display_name: str | None = None) -> None:
    import base64
    import hashlib
    from datetime import datetime, timezone
    import streamlit as st
    from clarte360_cp.connectors.gda_documents import GDAError, GDADocumentClient, load_gda_settings
    digest = hashlib.sha256(content).hexdigest()
    st.download_button("Télécharger le PDF", content, file_name=display_name,
        mime="application/pdf", key=f"cp_final_pdf_{kind}_{version}")
    if word_content is not None and word_display_name:
        st.download_button("Télécharger la version Word", word_content, file_name=word_display_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"cp_final_docx_{kind}_{version}")
    settings = load_gda_settings(st.secrets)
    token = str(st.session_state.get("gda_launch_token", ""))
    if not settings.configured or not token or not ctx.has_scope("CP_DELIVERABLE_RETURN"):
        st.caption("Remise dans l’espace partagé GDA disponible après activation du connecteur CP_V1.")
        return
    if st.button("Remettre le PDF final dans Gestion des Actions", key=f"cp_final_return_{kind}_{version}"):
        event_id = hashlib.sha256(f"{ctx.prescription_id}:{kind}:{version}:{digest}".encode()).hexdigest()[:48]
        event = {
            "event_id": event_id, "event_type": "CP_DELIVERABLE_READY", "scope": "CP_DELIVERABLE_RETURN",
            "tool_id": "COMPETENCES_PROJETS", "beneficiary_id": ctx.beneficiary_id,
            "action_id": ctx.action_id, "prescription_id": ctx.prescription_id,
            "participant_id": ctx.participant_id, "case_id": case_id, "document_id": document_id,
            "document_kind": kind, "document_version": str(version), "status": "FINALIZED",
            "mime_type": "application/pdf", "size_bytes": len(content), "sha256": digest,
            "created_at": datetime.now(timezone.utc).isoformat(), "audience": "BENEFICIARY_ONLY",
            "display_name": display_name, "content_b64": base64.b64encode(content).decode("ascii"),
        }
        try:
            receipt = GDADocumentClient(settings, token).return_finalized(event)
            from clarte360_cp.repositories.db import session_factory
            from clarte360_cp.repositories.gda_documents import record_gda_receipt
            with session_factory(_gda_engine())() as session:
                record_gda_receipt(session, ctx, case_id, event_id, receipt)
            st.success("Document remis dans l’espace partagé du dossier." if receipt["status"] == "ACCEPTED"
                       else "La remise était déjà enregistrée dans l’espace partagé.")
            st.caption(f"Référence de remise …{str(receipt.get('document_reference_id') or receipt['receipt_id'])[-8:]}")
        except GDAError as exc:
            st.error(str(exc))
        except Exception:
            st.warning("La remise GDA a peut-être abouti, mais C&P n’a pas enregistré son reçu local. Vérifiez la liste des documents avant de relancer; l’identifiant idempotent évite une seconde copie.")


def _short_ref(value: str | None, *, keep: int = 12) -> str:
    if not value:
        return "—"
    value = str(value)
    return value if len(value) <= keep else f"…{value[-keep:]}"


def _state_label(state: str | None) -> str:
    mapping = {
        "NON_DISPONIBLE": "Verrouillée",
        "DISPONIBLE": "Disponible",
        "EN_COURS": "En cours",
        "EN_ATTENTE_BENEFICIAIRE": "À relire par le bénéficiaire",
        "EN_ATTENTE_ACCOMPAGNATEUR": "Retour à traiter",
        "VALIDEE": "Terminée",
        "REOUVERTE": "Mise à jour — à revoir",
        "FIGEE_CLOTURE": "Clôturée",
    }
    return mapping.get(state or "", (state or "Non renseigné").replace("_", " ").title())


def _state_marker(state: str | None) -> str:
    if state in {"VALIDEE", "FIGEE_CLOTURE"}:
        return "✓"
    if state in {"EN_COURS", "REOUVERTE", "EN_ATTENTE_ACCOMPAGNATEUR", "EN_ATTENTE_BENEFICIAIRE"}:
        return "→"
    if state == "DISPONIBLE":
        return "•"
    return "○"


def _beneficiary_share_state(state: str | None) -> tuple[str, str]:
    if state == "EN_ATTENTE_BENEFICIAIRE":
        return "Publié au bénéficiaire", "À relire / confirmer"
    if state == "EN_ATTENTE_ACCOMPAGNATEUR":
        return "Retour bénéficiaire reçu", "À traiter par l'accompagnateur"
    if state in {"VALIDEE", "FIGEE_CLOTURE"}:
        return "Publié et validé", "Lecture disponible dans Mon parcours"
    if state == "REOUVERTE":
        return "Nouvelle version en préparation", "La version validée antérieure reste historisée"
    return "Non publié", "Travail de séance / préparation accompagnateur"


def _go(page: str, *, return_page: str | None = None) -> None:
    import streamlit as st
    if return_page is not None:
        st.session_state["navigation_return_page"] = return_page
    set_page(st.session_state, page)


def _button(label: str, page: str, *, key: str, primary: bool = False, return_page: str | None = None, disabled: bool = False) -> bool:
    import streamlit as st
    clicked = st.button(label, key=key, type="primary" if primary else "secondary", use_container_width=True, disabled=disabled)
    if clicked:
        _go(page, return_page=return_page)
        st.rerun()
    return clicked


def _phase_states(view: AccompanistDashboardView) -> dict[int, str]:
    return dict(view.snapshot.phase_states)


def render_context_bar(ctx, view: AccompanistDashboardView) -> None:
    import streamlit as st
    st.markdown(
        f"""
<div class="clarte-context-bar">
  <div><strong>Compétences & Projets</strong><br><span>Mode accompagnement</span></div>
  <div><strong>Bénéficiaire</strong><br><span>Dossier prescrit</span></div>
  <div><strong>Action</strong><br><span>N° {escape(str(ctx.action_no or "non renseigné"))}</span></div>
  <div><strong>Dossier</strong><br><span>{escape(view.snapshot.case_status.replace('_', ' ').title())}</span></div>
  <div><strong>Mise à jour</strong><br><span>En direct</span></div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_sidebar(view: AccompanistDashboardView) -> None:
    import streamlit as st
    current = st.session_state.get("navigation_page", "dashboard")
    states = _phase_states(view)
    with st.sidebar:
        st.markdown("### Parcours")
        if st.button("Tableau de bord", key="nav_dashboard", type="primary" if current == "dashboard" else "secondary", use_container_width=True):
            _go("dashboard"); st.rerun()
        if st.button("Documents", key="nav_documents", type="primary" if current == "documents" else "secondary", use_container_width=True):
            _go("documents", return_page=current if current != "documents" else "dashboard"); st.rerun()

        st.caption("PHASE PRÉLIMINAIRE")
        if st.button("Contexte du dossier", key="nav_entry_context", type="primary" if current == "entry_context" else "secondary", use_container_width=True):
            _go("entry_context"); st.rerun()
        for page, label in (
            ("entry_sources", "Vérifier les sources et le CV"),
            ("entry_preparation", "Préparer le questionnaire"),
            ("entry_joint_review", "Relire les réponses ensemble"),
        ):
            if st.button(label, key=f"nav_{page}", type="primary" if current == page else "secondary", use_container_width=True):
                _go(page); st.rerun()

        st.caption("DÉMARRER L’INVESTIGATION")
        for page, label in (("entry_ideas", "Recueillir les idées"),
                            ("entry_reperes", "Relire les repères personnels"),
                            ("entry_directions", "Choisir les premières directions")):
            if st.button(label, key=f"nav_{page}", type="primary" if current == page else "secondary", use_container_width=True):
                _go(page); st.rerun()

        for group in ("Investigation", "Conclusion"):
            st.caption(group.upper())
            for spec in [p for p in PHASE_SPECS if p.group == group]:
                state = states.get(spec.phase_no)
                label = f"{_state_marker(state)} {phase_display_number(spec.phase_no)}. {spec.short_label} — {_state_label(state)}"
                page = phase_page(spec.phase_no)
                disabled = state == "NON_DISPONIBLE"
                if st.button(label, key=f"nav_phase_{spec.phase_no}", type="primary" if current == page else "secondary", use_container_width=True, disabled=disabled):
                    _go(page); st.rerun()

        st.markdown("---")
        st.caption("Vous pouvez revenir à une étape précédente. La navigation ne vaut pas validation.")


def render_right_context(ctx, view: AccompanistDashboardView, *, page: str) -> None:
    import streamlit as st
    st.markdown("### Contexte utile")
    if view.snapshot.open_flags:
        st.warning(f"{view.snapshot.open_flags} point(s) à revoir")
    else:
        st.caption("Aucun point à revoir signalé.")

    if view.snapshot.active_tasks:
        st.write(f"**Actions à faire entre deux rendez-vous :** {view.snapshot.active_tasks}")
    else:
        st.write("**Actions à faire entre deux rendez-vous :** 0")

    st.write(f"**Sources vérifiées :** {view.introduced_sources}/{view.total_sources}")
    if view.snapshot.last_validation_at:
        value = view.snapshot.last_validation_at
        if isinstance(value, datetime):
            value = value.strftime("%d/%m/%Y %H:%M")
        st.write(f"**Dernière validation :** {value}")
    else:
        st.write("**Dernière validation :** aucune")

    if page != "documents":
        if st.button("Voir les documents", key=f"ctx_docs_{page}", use_container_width=True):
            _go("documents", return_page=page); st.rerun()
    with st.expander("Références techniques", expanded=False):
        st.caption(f"Dossier : {view.snapshot.case_code}")
        st.caption(f"Action n° {ctx.action_no or ctx.action_id}")
        st.caption(f"Prescription : {ctx.prescription_id}")


def render_dashboard(ctx, view: AccompanistDashboardView) -> None:
    import streamlit as st
    st.title("Tableau de bord du dossier")
    st.caption("Votre point d'entrée de séance : où en est le dossier, ce qui reste ouvert et ce qu'il est utile de faire maintenant.")

    main, side = st.columns([3.2, 1.15], gap="large")
    with main:
        st.markdown(
            f"""
<div class="clarte-next-action">
  <div class="clarte-eyebrow">PROCHAINE ACTION</div>
  <div class="clarte-next-title">{escape(choose_next_action(view.snapshot).title)}</div>
  <div class="clarte-muted">{escape(choose_next_action(view.snapshot).detail)}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        prep = read_preparation(ctx, view.snapshot.case_id)
        if prep.questionnaire is None:
            st.info("Avant d’inviter le bénéficiaire, préparez les questions sur ses idées professionnelles et ses repères personnels. Vous pourrez tout relire avant la mise à disposition.")
            _button("Préparer le questionnaire", "entry_preparation", key="dashboard_prep", primary=True)
        elif prep.active_answers and not prep.reviewed_in_session:
            st.info("Réponses du bénéficiaire reçues : préparer leur relecture en séance et la confirmation commune.")
            _button("Ouvrir la relecture en séance", "entry_joint_review", key="dashboard_joint", primary=True)
        else:
            _button("Ouvrir la prochaine action", "entry_preparation" if not prep.invitation_open else choose_next_action(view.snapshot).page, key="dashboard_next", primary=True)

        cols = st.columns(4)
        current_phase = view.snapshot.current_phase if view.snapshot.current_phase is not None else 0
        phase_state = dict(view.snapshot.phase_states).get(current_phase)
        items = (
            ("Étape en cours", f"{phase_display_number(current_phase)}. {PHASE_BY_NO.get(current_phase, PHASE_BY_NO[0]).short_label}", _state_label(phase_state)),
            ("Points ouverts", str(view.snapshot.open_flags), "À revoir" if view.snapshot.open_flags else "Aucun signalement"),
            ("Interséances", str(view.snapshot.active_tasks), f"{view.snapshot.submitted_tasks} à débriefer" if view.snapshot.submitted_tasks else "Aucun retour en attente"),
            ("Documents", f"{view.introduced_sources}/{view.total_sources}", "Sources introduites"),
        )
        for col, (title, value, note) in zip(cols, items):
            with col:
                st.markdown(f"<div class='clarte-kpi'><span>{escape(title)}</span><strong>{escape(value)}</strong><small>{escape(note)}</small></div>", unsafe_allow_html=True)

        st.markdown("### Parcours")
        states = _phase_states(view)
        groups = st.columns(3)
        group_specs = (
            ("Phase préliminaire", None),
            ("Investigation", "Investigation"),
            ("Conclusion", "Conclusion"),
        )
        for col, (title, group) in zip(groups, group_specs):
            with col:
                st.markdown(f"**{title}**")
                if group is None:
                    st.write("Vérifier le dossier et l’action")
                    st.write("Vérifier les sources et le CV")
                    st.write("Préparer le questionnaire et le relire ensemble")
                else:
                    for spec in [p for p in PHASE_SPECS if p.group == group]:
                        state = states.get(spec.phase_no)
                        st.write(f"{_state_marker(state)} {phase_display_number(spec.phase_no)}. {spec.short_label} — {_state_label(state)}")

        if view.snapshot.submitted_tasks:
            st.markdown("### À débriefer")
            st.info(f"{view.snapshot.submitted_tasks} retour(s) interséance sont prêts à être repris en séance.")
    with side:
        render_right_context(ctx, view, page="dashboard")


def render_documents(ctx, view: AccompanistDashboardView) -> None:
    import streamlit as st
    st.title("Documents du dossier")
    st.caption("Sources amont, CV et livrables restent identifiables par provenance et version. Aucun rapport n'est fusionné en un profil global.")
    main, side = st.columns([3.2, 1.15], gap="large")
    by_type = {d.artifact_type: d for d in view.snapshot.document_summaries}
    with main:
        for code, label in SOURCE_CARDS:
            item = by_type[code]
            status = "Disponible" if item.present else "Non introduit"
            detail = []
            if item.version_no is not None:
                detail.append(f"version {item.version_no}")
            if item.current_state:
                detail.append(item.current_state.replace("_", " ").lower())
            meta = " • ".join(detail) if detail else "provenance/version à renseigner lors de l'introduction"
            st.markdown(
                f"<div class='clarte-document-card'><strong>{escape(label)}</strong><span>{escape(status)}</span><small>{escape(meta)}</small></div>",
                unsafe_allow_html=True,
            )
        if view.snapshot.other_documents_count:
            st.caption(f"{view.snapshot.other_documents_count} autre(s) document(s) métier sont déjà rattachés au dossier.")
        st.info("Ces cartes résument les pièces rattachées au bilan C&P. Pour vérifier les documents réellement partagés dans Gestion des Actions, ouvrez « Vérifier les sources et le CV ». Le connecteur les liste et permet leur liaison lorsqu’il est configuré; son fonctionnement réel reste à vérifier sur le VPS de recette. Un nouveau document reste à relier au besoin du bilan avant usage.")
        return_page = st.session_state.get("navigation_return_page") or "dashboard"
        _button("Revenir à l'écran précédent", return_page, key="docs_return")
    with side:
        render_right_context(ctx, view, page="documents")


def render_entry_context(ctx, view: AccompanistDashboardView) -> None:
    import streamlit as st
    st.title("Vérifier le dossier avant de commencer")
    st.caption("Vérifiez que le dossier ouvert correspond bien au bénéficiaire et à l’action prescrite avant de commencer.")
    main, side = st.columns([3.2, 1.15], gap="large")
    with main:
        st.success("Contexte de lancement signé et cohérent avec le dossier ouvert.")
        st.markdown("#### Repères de la phase préliminaire")
        st.write(f"**Numéro de l’action :** {ctx.action_no or 'Non renseigné'}")
        st.write(f"**Votre accès :** {ctx.actor_role.value.title()}")
        st.caption("Ce dossier est ouvert depuis l’action prescrite dans Gestion des Actions.")
        st.info("Avant de poursuivre, vérifiez avec le bénéficiaire : 1) sa demande et son besoin; 2) le format, le rythme et les moyens adaptés; 3) les modalités du bilan, les règles de confidentialité et son consentement. Ces éléments sont à consigner dans le dossier de gestion des actions selon votre procédure.")
        st.caption("Cet écran vérifie le bon dossier et la bonne action. Il ne remplace pas l’enregistrement de la phase préliminaire dans le dossier de gestion.")
        _button("Continuer vers la préparation", "entry_sources", key="entry_context_next", primary=True)
    with side:
        render_right_context(ctx, view, page="entry_context")


def render_entry_sources(ctx, view: AccompanistDashboardView) -> None:
    import streamlit as st
    from clarte360_cp.connectors.gda_documents import GDAError, GDADocumentClient, load_gda_settings
    st.title("Sources amont et CV")
    st.caption("Vérifiez les documents disponibles et ceux qui sont nécessaires avant de commencer le travail sur le parcours.")
    main, side = st.columns([3.2, 1.15], gap="large")
    by_type = {d.artifact_type: d for d in view.snapshot.document_summaries}
    cv_present = by_type["CV_SOURCE"].present
    with main:
        settings = load_gda_settings(st.secrets)
        token = str(st.session_state.get("gda_launch_token", ""))
        linked_purposes = set()
        if settings.configured and token:
            try:
                gda = GDADocumentClient(settings, token)
                linked_purposes = _render_gda_document_workspace(ctx, st.session_state.case_id, gda)
            except GDAError as exc:
                st.warning(str(exc))
        else:
            st.info("La liste, l’ouverture et le dépôt dans l’espace documentaire GDA seront disponibles après activation du service CP_V1 côté Gestion des Actions. Aucun fichier n’est copié localement par C&P.")
        cv_present = cv_present or "CV_SOURCE" in linked_purposes
        if cv_present:
            st.success("Une référence CV est déjà enregistrée dans ce dossier C&P.")
        else:
            st.warning("Aucune référence CV n’est enregistrée dans ce dossier C&P. Elle devra être choisie dans l’espace partagé GDA avant l’étude détaillée du parcours.")
        cols = st.columns(2)
        for i, (code, label) in enumerate(SOURCE_CARDS):
            item = by_type[code]
            with cols[i % 2]:
                state = "Référence présente" if item.present else "Référence absente"
                st.markdown(f"<div class='clarte-source-card'><strong>{escape(label)}</strong><span>{escape(state)}</span><small>Référence enregistrée dans le dossier C&amp;P</small></div>", unsafe_allow_html=True)
        st.caption("PIP : seul le rapport ACCOMPAGNEMENT est admis. O*NET et le rapport PUBLIC sont exclus de C&P.")
        if cv_present:
            _button("Ouvrir le travail sur le parcours", "phase_0", key="entry_sources_next", primary=True)
        else:
            st.info("Le travail sur le CV s’ouvrira après liaison de sa référence GDA au besoin « CV source ».")
    with side:
        render_right_context(ctx, view, page="entry_sources")


def render_project_comparison(ctx, case_id: str) -> None:
    import streamlit as st
    data = read_go23(ctx, case_id)
    st.markdown("#### Comparaison qualitative des projets")
    st.caption("Complétez les constats établis ensemble. Aucun score, total, feu global ou classement automatique n’est calculé.")
    st.info("Le brouillon reste modifiable. Le partage crée une version visible par le bénéficiaire; toute correction ultérieure sera enregistrée dans une nouvelle version.")
    if not data["targets"]:
        st.info("Choisissez d’abord les métiers à étudier à l’étape 3 du parcours.")
        return
    previous = {(job, criterion): content for job, criterion, content in data["comparison_cells"]}
    rows = []
    with st.form("go23_comparison_form"):
        for job_id, label, code in data["targets"]:
            st.markdown(f"**{label}** · {code}")
            for criterion in CRITERIA:
                help_text = (
                    "Ne notez un diplôme ou titre comme obligatoire qu’avec une source officielle. "
                    "Un souhait d’employeur ou une offre ne constitue pas une obligation d’exercice. "
                    "Indiquez la source et la date consultées ; en cas de doute, écrivez « à vérifier »."
                    if criterion == "Diplôme ou titre officiellement obligatoire" else
                    "Pour les faits de marché ou d’accès, indiquez la source et sa date. Une information non vérifiée reste « à vérifier »."
                )
                content = st.text_area(criterion, value=previous.get((job_id, criterion), ""),
                    max_chars=2400, height=72, key=f"go23_{job_id}_{CRITERIA.index(criterion)}", help=help_text,
                    placeholder="Constat établi ensemble… Source / date lorsque pertinent…")
                rows.append({"job_target_id": job_id, "criterion": criterion, "content": content})
        save = st.form_submit_button("Enregistrer le brouillon")
        share = st.form_submit_button("Enregistrer et partager au bénéficiaire", type="primary")
    if save or share:
        try:
            version = save_comparison(ctx, case_id, rows, publish=share)
            st.success(f"Comparaison version {version} {'partagée' if share else 'enregistrée en brouillon'}.")
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
    if data["comparison_version"]:
        state = "partagée au bénéficiaire" if data["comparison_state"] == "PUBLIEE" else "brouillon interne"
        st.caption(f"Dernière version : {data['comparison_version']} · {state}")


def render_project_decision(ctx, case_id: str) -> None:
    import streamlit as st
    data = read_go23(ctx, case_id)
    st.markdown("#### Projet prioritaire et alternative éventuelle")
    st.info("La décision appartient au bénéficiaire. L’accompagnateur formalise ici ce qui a été exprimé en séance ; l’alternative reste facultative.")
    if data.get("decision_out_of_date"):
        st.warning("La comparaison a été actualisée depuis la dernière décision. Reprenez le choix en séance avant de poursuivre vers le plan d’action.")
    if not data["targets"]:
        st.info("Ajoutez un métier ROME avant de formaliser un choix.")
        return
    target_options = [row[0] for row in data["targets"]]
    labels = {row[0]: f"{row[1]} · {row[2]}" for row in data["targets"]}
    for kind, title in (("PRIORITAIRE", "Projet prioritaire"), ("ALTERNATIVE", "Alternative si elle est utile")):
        prior = data["decisions"].get(kind)
        decision_id = data.get("decision_ids", {}).get(kind)
        published = data.get("decision_published", {}).get(kind, False)
        if prior:
            status = "partagé au bénéficiaire" if published else "enregistré, à partager après relecture"
            st.caption(f"{title} : {status}.")
            if decision_id and not published and st.button(f"Partager {title.lower()}", key=f"go23_publish_{kind}", type="primary"):
                try:
                    publish_project_decision(ctx, case_id, decision_id=decision_id)
                    st.success("La décision est maintenant visible dans le parcours du bénéficiaire.")
                    st.rerun()
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
        with st.form(f"go23_decision_{kind}"):
            chosen = st.selectbox(title, target_options, index=target_options.index(prior[0]) if prior and prior[0] in target_options else 0,
                format_func=lambda x: labels[x], key=f"go23_select_{kind}")
            wording = st.text_area("Raisons et conditions formulées par le bénéficiaire", value=prior[1] if prior else "",
                max_chars=2000, height=90, key=f"go23_reason_{kind}")
            confirmed = st.checkbox("Cette position a été exprimée par le bénéficiaire en séance", key=f"go23_confirm_{kind}")
            submit = st.form_submit_button("Enregistrer cette décision", type="primary")
        if submit:
            if not confirmed:
                st.error("Confirmez que cette décision a bien été exprimée par le bénéficiaire en séance.")
            else:
                try:
                    record_project_decision(ctx, case_id, job_target_id=chosen, decision_type=kind, wording=wording)
                    st.success(f"{title} enregistré en note de séance. Relisez puis partagez-le explicitement au bénéficiaire.")
                    st.rerun()
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))


def render_action_plan(ctx, case_id: str) -> None:
    import streamlit as st
    data = read_action_plan(ctx, case_id)
    st.markdown("#### Plan d'action relié au projet prioritaire")
    st.info("Enregistrez un brouillon pendant la préparation. Le partage crée une version que le bénéficiaire peut relire; les modifications suivantes formeront une nouvelle version.")
    if data["decision"]:
        st.caption(f"Projet retenu : **{escape(data['decision'][0].title())}** · {escape(data['decision'][1])}")
    if data["state"]:
        label = "partagé au bénéficiaire" if data["state"] == "PUBLIEE" else "brouillon interne"
        st.info(f"Version {data['version_no']} · {label}")
        if not data.get("is_current", True):
            st.warning("Ce plan se rapporte à une ancienne comparaison. Reprenez le projet avec le bénéficiaire avant de le partager à nouveau.")
    old_items = list(data["items"])
    default_count = min(12, max(3, len(old_items)))
    count = st.number_input("Nombre d'actions à préparer", min_value=1, max_value=12,
                            value=default_count, step=1, key="go24_action_count")
    rows = []
    with st.form("go24_action_plan_form"):
        for index in range(int(count)):
            old = old_items[index] if index < len(old_items) else {}
            st.markdown(f"**Action {index + 1}**")
            action = st.text_input("Étape concrète", value=old.get("action", ""), max_chars=2400,
                                   key=f"go24_action_{index}", placeholder="Ex. Réaliser deux entretiens avec des professionnels du métier")
            cols = st.columns(3)
            due = cols[0].text_input("Échéance ou repère", value=old.get("due", "") or "", max_chars=80, key=f"go24_due_{index}")
            means = cols[1].text_input("Moyens / appui", value=old.get("means", "") or "", max_chars=2400, key=f"go24_means_{index}")
            expected = cols[2].text_input("Résultat attendu", value=old.get("expected", "") or "", max_chars=2400, key=f"go24_expected_{index}")
            rows.append({"action": action, "due": due, "means": means, "expected": expected})
        save = st.form_submit_button("Enregistrer le brouillon")
        share = st.form_submit_button("Enregistrer et partager au bénéficiaire", type="primary")
    if save or share:
        try:
            version = save_action_plan(ctx, case_id, rows, publish=share)
            st.success(f"Plan d'action version {version} {'partagé' if share else 'enregistré en brouillon'}.")
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
    if data.get("state") == "PUBLIEE" and data.get("is_current", True) and data.get("beneficiary_response") == "EXPLICITE":
        from clarte360_cp.reporting.conclusion_pdf import render_action_plan_pdf
        from clarte360_cp.reporting.conclusion_docx import render_action_plan_docx
        pdf = render_action_plan_pdf(data)
        docx = render_action_plan_docx(data)
        _render_final_deliverable(ctx, case_id, "PLAN_ACTION_FINAL", data.get("version_no") or 1,
            str(data.get("plan_id") or "plan"), f"Clarte360_plan_action_v{data.get('version_no') or 1}.pdf", pdf,
            word_content=docx, word_display_name=f"Clarte360_plan_action_v{data.get('version_no') or 1}.docx")


def render_detailed_results(ctx, case_id: str) -> None:
    import streamlit as st
    data = read_conclusion(ctx, case_id)
    current = data["results"] or {}
    values = current.get("content", {})
    st.markdown("#### Résultats détaillés du bilan")
    st.caption("Cette restitution décrit le parcours, les savoirs étayés, le projet et les conditions d'accès. Elle reste distincte de la synthèse finale.")
    st.info("Le brouillon reste modifiable. Le partage envoie une version au bénéficiaire pour relecture; toute correction ultérieure créera une nouvelle version.")
    if current:
        st.info(f"Version {current['version']} · {current['state'].replace('_', ' ').lower()}")
    rows = {}
    with st.form("go24_results_form"):
        for key, label in RESULT_FIELDS:
            help_text = "Une obligation de diplôme ou de titre exige une source officielle et sa date." if key == "diploma_source" else None
            rows[key] = st.text_area(label, value=values.get(key, ""), max_chars=8000, height=95,
                                     key=f"go24_result_{key}", help=help_text)
        draft = st.form_submit_button("Enregistrer le brouillon")
        publish = st.form_submit_button("Partager pour relecture du bénéficiaire", type="primary")
    if draft or publish:
        try:
            version = save_results(ctx, case_id, rows, publish=publish)
            st.success(f"Résultats détaillés version {version} {'partagés pour relecture' if publish else 'enregistrés en brouillon'}.")
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
    if current.get("state") in {"CONFIRMEE", "FINALISEE"}:
        from clarte360_cp.reporting.conclusion_pdf import render_results_pdf
        from clarte360_cp.reporting.conclusion_docx import render_results_docx
        pdf = render_results_pdf(current)
        docx = render_results_docx(current)
        _render_final_deliverable(ctx, case_id, "RESULTATS_DETAILLES_FINAL", current.get("version") or 1,
            current.get("id") or "resultats", f"Clarte360_resultats_v{current.get('version') or 1}.pdf", pdf,
            word_content=docx, word_display_name=f"Clarte360_resultats_v{current.get('version') or 1}.docx")


def render_final_synthesis(ctx, case_id: str) -> None:
    import streamlit as st
    data = read_conclusion(ctx, case_id)
    current = data["synthesis"] or {}
    values = current.get("content", {})
    st.markdown("#### Synthèse finale")
    st.caption("La synthèse reprend les conclusions utiles au bénéficiaire. Elle n'est finalisée qu'après sa relecture.")
    st.info("Le brouillon reste modifiable. Le partage envoie une version au bénéficiaire pour relecture; les corrections ultérieures seront enregistrées dans une nouvelle version.")
    if current:
        st.info(f"Version {current['version']} · {current['state'].replace('_', ' ').lower()}")
    rows = {}
    with st.form("go24_synthesis_form"):
        for key, label in SYNTHESIS_FIELDS:
            rows[key] = st.text_area(label, value=values.get(key, ""), max_chars=8000, height=90,
                                     key=f"go24_synthesis_{key}")
        draft = st.form_submit_button("Enregistrer le brouillon")
        publish = st.form_submit_button("Partager pour relecture du bénéficiaire", type="primary")
    if draft or publish:
        try:
            version = save_synthesis(ctx, case_id, rows, publish=publish)
            st.success(f"Synthèse version {version} {'partagée pour relecture' if publish else 'enregistrée en brouillon'}.")
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
    if current.get("state") == "CONFIRMEE":
        st.warning("La finalisation établira cette version comme synthèse de référence. Vérifiez la relecture du bénéficiaire et le contenu avant de continuer. Une correction ultérieure nécessitera une nouvelle version.")
        finalize_confirm = st.checkbox("Je confirme que cette version relue peut devenir la synthèse de référence.", key=f"go24_finalize_confirm_{current['id']}")
        if st.button("Finaliser cette version de référence", type="primary", key="go24_finalize_synthesis", disabled=not finalize_confirm):
            try:
                finalize_synthesis(ctx, case_id, artifact_version_id=current["id"])
                st.success("La synthèse est finalisée et conservée comme version de référence.")
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
    if current.get("state") == "FINALISEE":
        from clarte360_cp.reporting.conclusion_pdf import render_synthesis_pdf
        from clarte360_cp.reporting.conclusion_docx import render_synthesis_docx
        pdf = render_synthesis_pdf(current)
        docx = render_synthesis_docx(current)
        _render_final_deliverable(ctx, case_id, "SYNTHESE_FINALE", current.get("version") or 1,
            current.get("id") or "synthese", f"Clarte360_synthese_finale_v{current.get('version') or 1}.pdf", pdf,
            word_content=docx, word_display_name=f"Clarte360_synthese_finale_v{current.get('version') or 1}.docx")


def render_bilan_closure(ctx, case_id: str) -> None:
    import streamlit as st
    from datetime import date
    data = read_conclusion(ctx, case_id)
    st.markdown("#### Clôture du bilan et suivi à six mois")
    if data["closed"]:
        st.success("Le bilan est clôturé. Le suivi est préparé selon la date affichée ci-dessous.")
    else:
        st.caption("La clôture intervient après le partage du plan d'action, la confirmation des résultats et la finalisation de la synthèse.")
    today = date.today()
    month = today.month + 6
    year = today.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(today.day, 28)
    target = date(year, month, day)
    with st.form("go24_followup_form"):
        planned = st.date_input("Date proposée pour le point de suivi (environ six mois)",
                                value=target, min_value=date(year, month, 1),
                                key="go24_followup_date")
        prepare = st.form_submit_button("Enregistrer le suivi à six mois")
    retention = st.selectbox("Traitement des documents à la clôture",
        options=["CONSERVATION_SELON_REGLES", "DESTRUCTION_DEMANDEE"],
        format_func=lambda x: "Conservation selon les règles applicables" if x == "CONSERVATION_SELON_REGLES" else "Destruction à traiter selon la procédure applicable")
    if prepare:
        try:
            save_followup_plan(ctx, case_id, planned_for=planned.isoformat())
            st.success("Le suivi a été préparé. Aucun rappel externe n'est envoyé tant que le connecteur Hub/GDA n'est pas raccordé.")
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
    if data["followup"]:
        st.info(f"Suivi prévu le {data['followup']['date']} · état : {data['followup']['status']}")
    if data.get("followup_response"):
        st.markdown("**Retour du bénéficiaire**")
        st.write(data["followup_response"].get("comment", ""))
    if not data["closed"]:
        st.warning("La clôture termine le dossier, enregistre le traitement des documents et programme le suivi à six mois. Vérifiez les livrables, le suivi enregistré et le choix de conservation avant de confirmer.")
        close_confirm = st.checkbox("J’ai vérifié les livrables et je confirme la clôture du bilan.", key="go24_close_confirm")
    else:
        close_confirm = False
    if not data["closed"] and st.button("Clôturer définitivement le bilan", type="primary", key="go24_close_bilan", disabled=not close_confirm):
        try:
            close_bilan(ctx, case_id, retention_action=retention)
            st.success("Le bilan est clôturé et le suivi à six mois est planifié dans le dossier.")
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))


def _render_phase_pattern(phase_no: int, ctx=None, case_id: str | None = None) -> None:
    import streamlit as st
    if phase_no == 0:
        st.markdown("#### Enrichissement du parcours professionnel")
        _render_cv_enrichment_after_cav3(ctx, case_id or "")
        render_career_enrichment(ctx, case_id or "")
    elif phase_no == 3:
        st.markdown("#### Synthèse avant le détail ROME")
        st.info("Le rapprochement porte d’abord sur les savoirs et compétences attendus par le ROME et les preuves du parcours : expériences, études, formations et apprentissages personnels. Un diplôme est une condition obligatoire uniquement si une source officielle confirme cette obligation pour exercer le métier.")
        cols = st.columns(4)
        for col, (label, value) in zip(cols, (("Acquis", "—"), ("À confirmer", "—"), ("Non documentés", "—"), ("À développer", "—"))):
            col.markdown(f"<div class='clarte-kpi'><span>{escape(label)}</span><strong>{escape(value)}</strong><small>Calculé au GO-22</small></div>", unsafe_allow_html=True)
        with st.expander("Voir le détail ROME et la provenance", expanded=False):
            st.caption("Le détail sera alimenté par les snapshots ROME et le rapprochement du GO-22.")
    elif phase_no == 4:
        st.markdown("#### Entretien séquentiel")
        st.markdown("<div class='clarte-question'><span>QUESTION 1 / —</span><strong>Le prochain point utile à confirmer apparaîtra ici.</strong><small>Une seule question centrale à la fois ; la liste complète reste repliée.</small></div>", unsafe_allow_html=True)
    elif phase_no == 5:
        st.markdown("#### Faisabilité : quatre lectures séparées")
        for title, body in (
            ("Savoirs et compétences", "Comparer les attendus ROME aux acquis étayés par le parcours, les études, les formations et les apprentissages personnels."),
            ("Conditions officiellement obligatoires", "Vérifier auprès d’une source officielle les diplômes, titres ou autorisations réellement obligatoires pour exercer."),
            ("Sources officielles", "ROME, marché, offres et autres données datées."),
            ("Éclairages amont", "Valeurs, moteurs, préférences et profil uniquement lorsqu'ils éclairent une question."),
            ("Reste à vérifier", "Enquête métier, immersion, apprentissage à prévoir ou information manquante. Une formation n’est proposée que si elle répond à une obligation vérifiée ou à un besoin de savoirs/compétences que le bénéficiaire souhaite combler."),
        ):
            st.markdown(f"<div class='clarte-card'><strong>{escape(title)}</strong><span>{escape(body)}</span></div>", unsafe_allow_html=True)
    elif phase_no == 6:
        render_project_comparison(ctx, view.snapshot.case_id)
    elif phase_no == 7:
        render_project_decision(ctx, view.snapshot.case_id)
    elif phase_no == 8:
        render_action_plan(ctx, case_id or "")
    elif phase_no == 9:
        render_detailed_results(ctx, case_id or "")
    elif phase_no == 10:
        render_final_synthesis(ctx, case_id or "")
    elif phase_no == 11:
        render_bilan_closure(ctx, case_id or "")


def render_phase(ctx, view: AccompanistDashboardView, phase_no: int) -> None:
    import streamlit as st
    spec = PHASE_BY_NO[phase_no]
    state = dict(view.snapshot.phase_states).get(phase_no)
    page = phase_page(phase_no)
    st.title(f"{phase_display_number(phase_no)}. {spec.label}")
    st.caption(spec.finality)
    main, side = st.columns([3.2, 1.15], gap="large")
    with main:
        st.markdown(f"<div class='clarte-status-line'><strong>État de la phase</strong><span>{escape(_state_label(state))}</span></div>", unsafe_allow_html=True)
        if phase_no == 2:
            render_rome_target_selection(ctx, view.snapshot.case_id)
        elif phase_no == 3:
            render_rome_matching(ctx, view.snapshot.case_id)
        elif phase_no == 4:
            render_rome_clarification(ctx, view.snapshot.case_id)
        elif phase_no == 5:
            render_rome_investigations(ctx, view.snapshot.case_id)
        else:
            _render_phase_pattern(phase_no, ctx, view.snapshot.case_id)

        if phase_no == 0:
            feedback = read_career_phase_feedback(ctx, view.snapshot.case_id)
            if feedback and feedback["decision"] == "CORRECTION_DEMANDEE":
                st.warning("Le bénéficiaire a demandé une correction du parcours partagé.")
                if feedback.get("comment"):
                    st.markdown("**Remarque du bénéficiaire**")
                    st.info(feedback["comment"])
                    st.caption("Reprenez les cartes concernées avec le bénéficiaire, puis validez à nouveau cette étape avant de poursuivre.")
            elif feedback and feedback["decision"] == "CONFIRME":
                st.success("Le bénéficiaire a confirmé cette version du parcours.")

        share_title, share_detail = _beneficiary_share_state(state)
        st.markdown("### Résultat partagé avec le bénéficiaire")
        st.markdown(
            f"<div class='clarte-readonly'><strong>{escape(share_title)}</strong><span>{escape(share_detail)}</span><small>Le bénéficiaire consulte le résultat propre de cette étape dans Mon parcours. Il ne modifie pas le travail de séance ; seules les validations prévues ou les actions hors séance lui donnent une action propre.</small></div>",
            unsafe_allow_html=True,
        )
        if phase_no == 0:
            st.caption("Sortie attendue : Parcours professionnel enrichi — lecture écran, PDF/Impression et export Word modifiable lorsque le moteur documentaire sera branché.")
        if phase_no not in {6, 7, 8, 9, 10}:
            st.caption("La publication du résultat apparaît ici dès que le livrable de cette phase est raccordé.")

        st.markdown("### Validation de l'étape")
        st.write(f"**Validation attendue :** {spec.validation_label}")
        if state == "NON_DISPONIBLE":
            blockers = ("Validez d'abord la phase précédente pour ouvrir cette étape.",)
        else:
            try:
                blockers = phase_readiness(ctx, view.snapshot.case_id, phase_no)
            except (ValueError, PermissionError) as exc:
                blockers = (str(exc),)
        if blockers:
            st.info("À compléter avant la validation :")
            for blocker in blockers:
                st.markdown(f"- {blocker}")
        elif state in {"VALIDEE", "FIGEE_CLOTURE"}:
            st.success("Cette étape est validée et son historique est conservé.")
        else:
            with st.expander("Terminer cette étape", expanded=False):
                note = st.text_area("Constat de fin de phase et points restant à suivre", max_chars=2000,
                    height=90, key=f"phase_validation_note_{phase_no}",
                    placeholder="Résumez ce qui a été établi avec le bénéficiaire et ce qui reste ouvert.")
                if st.button("Marquer l’étape comme terminée", key=f"validate_phase_{phase_no}", type="primary"):
                    try:
                        validate_phase(ctx, view.snapshot.case_id, phase_no, note=note)
                        st.success("Phase validée. La suivante est maintenant disponible.")
                        st.rerun()
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))

        nav_cols = st.columns(2)
        with nav_cols[0]:
            _button("Retour au tableau de bord", "dashboard", key=f"phase_back_{phase_no}")
        with nav_cols[1]:
            next_phase = PHASE_NEXT.get(phase_no)
            if next_phase is not None:
                next_state = dict(view.snapshot.phase_states).get(next_phase)
                _button("Continuer vers l'étape suivante", phase_page(next_phase), key=f"phase_next_{phase_no}", disabled=next_state == "NON_DISPONIBLE")
    with side:
        render_right_context(ctx, view, page=page)


def render_accompanist_app(ctx, bootstrap) -> None:
    import streamlit as st
    view = build_accompanist_dashboard(bootstrap.case_id)
    render_context_bar(ctx, view)
    render_live_sync_status(ctx, bootstrap.case_id, compact=True)
    render_sidebar(view)
    page = st.session_state.get("navigation_page", "dashboard")
    if page == "home":
        page = "dashboard"
        st.session_state["navigation_page"] = page

    if page == "dashboard":
        render_dashboard(ctx, view)
    elif page == "documents":
        render_documents(ctx, view)
    elif page == "entry_context":
        render_entry_context(ctx, view)
    elif page == "entry_sources":
        render_entry_sources(ctx, view)
    elif page == "entry_preparation":
        render_questionnaire_builder(ctx, bootstrap.case_id)
    elif page == "entry_joint_review":
        render_joint_review(ctx, bootstrap.case_id)
    elif page == "entry_ideas":
        render_ideas(ctx, bootstrap.case_id)
    elif page == "entry_reperes":
        by_type = {d.artifact_type: d.present for d in view.snapshot.document_summaries}
        render_reperes(ctx, bootstrap.case_id, by_type)
    elif page == "entry_directions":
        render_cav3_source_summary(ctx, bootstrap.case_id)
        render_directions(ctx, bootstrap.case_id)
    elif page.startswith("phase_"):
        try:
            phase_no = int(page.split("_", 1)[1])
        except ValueError:
            phase_no = 0
        render_phase(ctx, view, phase_no)
    else:
        _go("dashboard")
        st.rerun()
