"""GO4: one Quality action, from creation through closure, in existing portals.

Widgets never grant permissions. Every read, mutation and attachment/export is
resolved by quality_service using the active, server-validated account. Drafts
and their original row version survive validation errors and concurrent edits.
"""
from __future__ import annotations

from datetime import date
from copy import deepcopy
import inspect
import logging
import uuid

import pandas as pd
import streamlit as st

import quality_service as quality


STATUS_LABELS = {
    "NOUVEAU": "Nouveau", "EN_TRAITEMENT": "En cours", "EN_ATTENTE": "En attente",
    "A_VERIFIER": "À vérifier", "CLOTURE": "Clôturé", "REFUSE": "Refusé",
    "CLASSE_SANS_SUITE": "Classé sans suite",
}
NATURE_LABELS = {"PREVENTIVE": "Prévention", "CORRECTIVE": "Correction", "AMELIORATION": "Amélioration"}
ORIGIN_LABELS = {
    "INTERNE": "Administration / initiative interne", "PREVENTION": "Prévention spontanée",
    "AUDIT_INTERNE": "Audit interne", "AUDIT_EXTERNE": "Audit externe",
    "QUESTIONNAIRE": "Enquête / questionnaire", "VEILLE": "Veille",
    "RECLAMATION": "Réclamation", "SIGNALEMENT": "Signalement / difficulté",
    "SIGNALEMENT_INTERVENANT": "Intervenant", "SIGNALEMENT_BENEFICIAIRE": "Bénéficiaire", "DEMANDE_CLIENT": "Client",
    "DIFFICULTE": "Difficulté", "LEGACY": "Historique repris",
}
CLOSED = {"CLOTURE", "REFUSE", "CLASSE_SANS_SUITE"}
ENDED_STEPS = {"TERMINEE", "ANNULEE", "VERIFIED", "ABANDONED"}
DATE_FORMAT = "DD/MM/YYYY"


def _dismiss_dialog():
    key = st.session_state.pop("go4_active_dialog", None)
    if key:
        st.session_state.pop(key, None)


# The RC2 accepts Streamlit 1.x. Use the documented dismissal callback where
# available; older releases still provide native dialogs and fragment reruns.
_DIALOG_OPTIONS = {"width": "large"}
_HAS_DISMISS_CALLBACK = "on_dismiss" in inspect.signature(st.dialog).parameters
if _HAS_DISMISS_CALLBACK:
    _DIALOG_OPTIONS["on_dismiss"] = _dismiss_dialog


def _key(actor, key):
    # Do not use email addresses, subject names or confidential text in DOM keys.
    context = uuid.uuid5(uuid.NAMESPACE_OID, f"{actor.role}:{actor.subject_id}:{actor.organization_id}").hex[:16]
    return f"go4_{context}_{key}"


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except (TypeError, ValueError):
        return None


def _date_label(value):
    day = _date(value)
    return day.strftime("%d/%m/%Y") if day else "—"


def _timestamp(engine, actor, value, action_id=None):
    if not value:
        return "—"
    from regional_settings import format_timestamp
    from services import get_regional_preferences
    return format_timestamp(value, get_regional_preferences(engine, action_id))


def _error(exc):
    if isinstance(exc, (ValueError, PermissionError, FileNotFoundError)):
        st.error(str(exc))
    else:
        # Only an incident reference and exception class enter this technical log.
        reference = uuid.uuid4().hex[:10].upper()
        logging.getLogger(__name__).error("quality_ui incident=%s type=%s", reference, type(exc).__name__)
        st.error(f"Enregistrement indisponible. Votre saisie est conservée. Référence : {reference}.")


def actor_for_space(engine, role, subject_id, *, action_id=None, key="space", focus_event_id=None):
    """Select only organizations derived from this active account by the service."""
    organizations = quality.available_organizations(engine, role, subject_id)
    if not organizations:
        st.info("Aucun organisme habilité pour ce compte. Contactez votre interlocuteur habituel.")
        return None
    context_key = f"go4_org_{role}_{key}"
    by_id = {int(row["id"]): row for row in organizations}
    if focus_event_id is not None:
        for organization_id in by_id:
            candidate = quality.QualityActor(role, subject_id, organization_id)
            try:
                quality.get_action(engine, candidate, focus_event_id)
                st.session_state[context_key] = organization_id
                break
            except (ValueError, PermissionError):
                continue
    if st.session_state.get(context_key) not in by_id:
        st.session_state[context_key] = next(iter(by_id))
    if len(by_id) > 1:
        org_id = st.selectbox("Organisme de la demande", list(by_id),
                              format_func=lambda value: by_id[value]["name"], key=context_key)
    else:
        org_id = next(iter(by_id))
        st.caption(f"Organisme : {by_id[org_id]['name']}")
    actor = quality.QualityActor(role, subject_id, org_id)
    quality.require_actor(engine, actor)
    # A contextual training can belong to another authorized organization. Derive
    # its organization only by listing the actor's authorized trainings, never by
    # trusting an unverified action id or revealing a foreign training title.
    if action_id is not None:
        for organization_id in by_id:
            candidate = quality.QualityActor(role, subject_id, organization_id)
            if any(int(row["id"]) == int(action_id) for row in quality.available_trainings(engine, candidate)):
                return candidate
        raise PermissionError("Cette formation n’est plus accessible pour votre compte.")
    return actor


def render_quality_workspace(engine, role, subject_id, *, action_id=None, key="space"):
    """Personal requests and explicitly delegated missions; no global case list."""
    try:
        focus = st.session_state.pop("j4_focus_event_id", None)
        actor = actor_for_space(engine, role, subject_id, action_id=action_id, key=key, focus_event_id=focus)
        if actor is None:
            return
        title = "Mes actions et missions Qualité" if role == "TRAINER" else "Mes demandes Qualité"
        st.subheader(title)
        st.caption("Retrouvez votre demande, ses réponses et son avancement au même endroit.")
        render_quality_plan(engine, actor, action_id=action_id, key=key, focus_event_id=focus)
    except Exception as exc:
        _error(exc)


def _open_dialog(engine, actor, key, mode, event_id=None):
    case = quality.get_action(engine, actor, event_id) if event_id is not None else None
    state = {"mode": mode, "event_id": event_id, "case": case, "show": True,
             "expected_version": case["event"]["row_version"] if case else None,
             "command_id": uuid.uuid4().hex, "draft_id": uuid.uuid4().hex[:12]}
    state["widget_prefix"] = f"{key}_{state['draft_id']}"
    st.session_state[f"{key}_dialog"] = state
    st.session_state["go4_active_dialog"] = f"{key}_dialog"


def _saved(key, message, event_id=None):
    st.session_state[f"{key}_flash"] = message
    if event_id is not None:
        st.session_state[f"{key}_next_selected"] = int(event_id)
    st.session_state.pop(f"{key}_dialog", None)
    st.session_state.pop("go4_active_dialog", None)
    st.rerun()


def _check_version(engine, actor, state):
    """Always recheck authorization; do not silently replace the edited version."""
    if state["event_id"] is None:
        quality.require_actor(engine, actor)
        return
    latest = quality.get_action(engine, actor, state["event_id"])
    if latest["event"]["row_version"] != state["expected_version"]:
        st.warning("Cette action a changé depuis l’ouverture de la fenêtre. Votre saisie est conservée. Relisez l’actualisation avant de l’enregistrer.")
        with st.expander("Version actuellement enregistrée", expanded=True):
            event = latest["event"]
            st.write(f"{STATUS_LABELS.get(event['status'], event['status'])} · {event.get('subject') or ''}")
            for message in latest.get("messages", [])[-3:]:
                st.write(message.get("message") or "")
        if st.button("Relire la version actualisée", key=f"rebase_{state['draft_id']}"):
            old_event = state["case"]["event"]
            new_event = latest["event"]
            fields = {"status": "status", "title": "subject", "description": "description",
                      "due": "due_at", "nature": "action_nature", "classification": "data_classification"}
            for widget_field, event_field in fields.items():
                widget_key = f"{state['widget_prefix']}_{widget_field}"
                old_value = _date(old_event.get(event_field)) if widget_field == "due" else old_event.get(event_field)
                new_value = _date(new_event.get(event_field)) if widget_field == "due" else new_event.get(event_field)
                if widget_field in ("title", "description"):
                    old_value, new_value = old_value or "", new_value or ""
                # Rebase only fields the user has not changed. Their comment,
                # closure summary and deliberately edited values remain intact.
                if widget_key in st.session_state and st.session_state[widget_key] == old_value:
                    st.session_state[widget_key] = new_value
            state["expected_version"] = latest["event"]["row_version"]
            state["case"] = latest
            st.info("Version actualisée relue. Vos champs saisis restent disponibles ; vérifiez-les avant d’enregistrer.")


@st.dialog("Action Qualité", **_DIALOG_OPTIONS)
def _action_dialog(engine, actor, key, *, action_id=None):
    state = st.session_state[f"{key}_dialog"]
    try:
        _check_version(engine, actor, state)
    except Exception as exc:
        _error(exc)
        return
    mode, event_id = state["mode"], state["event_id"]
    widget = f"{key}_{state['draft_id']}"
    case = state.get("case") or {}
    event = case.get("event", {})
    permissions = case.get("permissions", {})
    version = state["expected_version"]
    command_id = state["command_id"]
    staff = actor.role in ("ADMIN", "TRAINER")

    try:
        if mode == "create":
            st.subheader("Nouvelle action" if staff else "Nouvelle demande")
            choices = quality.available_trainings(engine, actor)
            trainings = {int(row["id"]): row for row in choices}
            default_action = int(action_id) if action_id is not None and int(action_id) in trainings else None
            with st.form(f"{widget}_form", clear_on_submit=False):
                title = st.text_input("Action à réaliser" if staff else "Votre demande", max_chars=250,
                                      key=f"{widget}_title")
                description = st.text_area("Contexte ou résultat attendu (facultatif)" if staff else "Votre message",
                                           key=f"{widget}_description")
                nature = st.selectbox("Nature", list(NATURE_LABELS), format_func=NATURE_LABELS.get,
                                      key=f"{widget}_nature") if staff else "AMELIORATION"
                due = st.date_input("Échéance (facultative)", value=None, format=DATE_FORMAT,
                                    key=f"{widget}_due") if staff else None
                with st.expander("Lier à une formation ou un bilan (facultatif)", expanded=default_action is not None):
                    options = [None] + list(trainings)
                    attached = st.selectbox("Formation ou bilan", options, index=options.index(default_action),
                        format_func=lambda value: "Générale / sans rattachement" if value is None else
                        f"{trainings[value]['action_no']} — {trainings[value]['title']}", key=f"{widget}_training")
                origin = "INTERNE"
                classification = "REAL"
                sensitivity = "NORMAL"
                if actor.role == "ADMIN":
                    with st.expander("Origine et confidentialité"):
                        origin = st.selectbox("Origine", list(ORIGIN_LABELS), format_func=ORIGIN_LABELS.get,
                                              key=f"{widget}_origin")
                        restricted = st.checkbox("Accès restreint aux personnes expressément habilitées", key=f"{widget}_restricted")
                        sensitivity = "RESTRICTED" if restricted else "NORMAL"
                        is_test = st.checkbox("Essai TEST : exclu des statistiques réelles", key=f"{widget}_test")
                        classification = "TEST" if is_test else "REAL"
                st.caption("Une seule ligne. Une prévention peut rester sans incident ni formation ; elle pourra être confiée ensuite.")
                submitted = st.form_submit_button("Créer", type="primary")
            if submitted:
                new_id = quality.create_action(engine, actor, title, description, origin=origin, nature=nature,
                    action_id=attached, classification=classification, command_id=command_id,
                    due_at=due.isoformat() if due else None, sensitivity=sensitivity)
                _saved(key, "Action enregistrée dans le plan unique." if staff else "Votre demande est enregistrée.", new_id)

        elif mode == "update":
            st.subheader(f"{'Mettre à jour' if staff else 'Répondre à'} {event['public_id']}")
            with st.form(f"{widget}_form", clear_on_submit=False):
                comment = st.text_area("Votre avancée" if staff else "Votre réponse", key=f"{widget}_comment")
                audience_options = {"PUBLIC": "Demandeur et personnes habilitées"}
                if permissions.get("internal"):
                    audience_options["INTERNAL"] = "Note interne uniquement"
                audience = st.selectbox("Qui peut lire cette avancée ?", list(audience_options),
                    format_func=audience_options.get, key=f"{widget}_audience") if len(audience_options) > 1 else "PUBLIC"
                changes = {}
                if permissions.get("update") and actor.role == "ADMIN" and event["status"] not in CLOSED:
                    statuses = [value for value in STATUS_LABELS if value not in CLOSED]
                    status = st.selectbox("Statut", statuses, index=statuses.index(event["status"]) if event["status"] in statuses else 0,
                                           format_func=STATUS_LABELS.get, key=f"{widget}_status")
                    changes["status"] = status
                    st.caption("Pour terminer l’action, utilisez Clôturer : bilan et étapes se traitent ensemble.")
                    if actor.role == "ADMIN":
                        with st.expander("Échéance et contenu"):
                            title = st.text_input("Action à réaliser", value=event.get("subject") or "", key=f"{widget}_title")
                            description = st.text_area("Contexte", value=event.get("description") or "", key=f"{widget}_description")
                            due = st.date_input("Échéance", value=_date(event.get("due_at")), format=DATE_FORMAT, key=f"{widget}_due")
                            nature = st.selectbox("Nature", list(NATURE_LABELS),
                                index=list(NATURE_LABELS).index(event.get("action_nature")) if event.get("action_nature") in NATURE_LABELS else 0,
                                format_func=NATURE_LABELS.get, key=f"{widget}_nature")
                            changes.update(title=title, description=description, due_at=due.isoformat() if due else "", nature=nature)
                            classification = st.selectbox("Qualification des données", ["REAL", "TEST", "A_EXAMINER"],
                                index=["REAL", "TEST", "A_EXAMINER"].index(event.get("data_classification") or "REAL"),
                                format_func=lambda value: {"REAL": "RÉEL", "TEST": "TEST", "A_EXAMINER": "À examiner"}[value], key=f"{widget}_classification")
                            changes["classification"] = classification
                submitted = st.form_submit_button("Enregistrer", type="primary")
            if submitted:
                changed = quality.update_action(engine, actor, event_id, expected_version=version,
                    comment=comment, audience=audience, **changes)
                _saved(key, "Avancée enregistrée." if changed else "Aucun changement à enregistrer.", event_id)

        elif mode == "close":
            st.subheader(f"Clôturer {event['public_id']}")
            st.caption("Un seul bilan et une seule confirmation. Toutes les étapes encore ouvertes se règlent ici.")
            remaining = [step for step in case.get("steps", []) if step.get("status") not in ENDED_STEPS]
            with st.form(f"{widget}_form", clear_on_submit=False):
                summary = st.text_area("Travail réalisé et résultat constaté", key=f"{widget}_summary")
                outcomes = {}
                if remaining:
                    st.markdown("#### Les étapes encore en suivi")
                    for step in remaining:
                        st.markdown(f"**{step.get('title') or 'Étape'}**")
                        if step.get("description"):
                            st.write(step["description"])
                        options = {"": "Choisir l’issue de cette étape", "VERIFIED": "Réalisée et vérifiée",
                                   "ABANDONED": "Abandonnée / remplacée", "REMAINING": "Il reste du travail"}
                        outcome = st.selectbox(f"Issue — {step.get('title') or 'Étape'}", list(options),
                            index=0, format_func=options.get, key=f"{widget}_step_{step['id']}")
                        reason = st.text_input("Motif si cette étape est abandonnée", key=f"{widget}_reason_{step['id']}")
                        outcomes[int(step["id"])] = {"outcome": outcome, "reason": reason}
                    st.caption("Le bilan commun justifie les étapes déclarées réalisées et vérifiées. Il n’est pas à recopier.")
                with st.expander("Conclusion particulière (si nécessaire)"):
                    conclusion = st.selectbox("Conclusion", ["RESOLVED", "CANCELLED", "NO_FOLLOWUP"],
                        format_func=lambda value: {"RESOLVED": "Résolue", "CANCELLED": "Annulée avec motif", "NO_FOLLOWUP": "Sans suite avec motif"}[value], key=f"{widget}_conclusion")
                    st.caption("Une annulation ou une non-suite sera distinguée d’une action résolue.")
                submitted = st.form_submit_button("Confirmer la clôture", type="primary")
            if submitted:
                quality.close_action(engine, actor, event_id, expected_version=version, summary=summary,
                                     step_outcomes=outcomes, outcome=conclusion, command_id=command_id)
                _saved(key, "Clôture enregistrée. Cette action conserve sa référence et son historique.", event_id)

        elif mode == "reopen":
            st.subheader(f"Rouvrir {event['public_id']}")
            with st.form(f"{widget}_form", clear_on_submit=False):
                reason = st.text_area("Pourquoi rouvrir ?", key=f"{widget}_reason")
                st.caption("La même ligne reprend son suivi. Les anciennes dates et conclusions restent dans l’historique.")
                submitted = st.form_submit_button("Rouvrir cette action", type="primary")
            if submitted:
                quality.reopen_action(engine, actor, event_id, expected_version=version, reason=reason, command_id=command_id)
                _saved(key, "Action rouverte avec la même référence.", event_id)

        elif mode == "assign":
            st.subheader(f"Confier {event['public_id']}")
            candidates = quality.eligible_delegates(engine, actor, event_id)
            if not candidates:
                st.info("Aucune personne active habilitée pour cette action. Les habilitations se gèrent dans les comptes existants.")
                return
            with st.form(f"{widget}_form", clear_on_submit=False):
                selected = st.selectbox("À qui ?", range(len(candidates)),
                    format_func=lambda index: candidates[index]["label"], index=None,
                    placeholder="Choisir une personne habilitée", key=f"{widget}_person")
                expected = st.text_area("Résultat attendu", value=event.get("expected_result") or "", key=f"{widget}_expected")
                due = st.date_input("Pour quand ? (facultatif)", value=_date(event.get("due_at")), format=DATE_FORMAT, key=f"{widget}_due")
                st.caption("La personne accepte la mission ou indique une impossibilité. La validation finale reste à l’administration habilitée.")
                submitted = st.form_submit_button("Confier et notifier", type="primary")
            if submitted:
                if selected is None:
                    raise ValueError("Choisissez une personne habilitée.")
                person = candidates[selected]
                quality.assign_action(engine, actor, event_id, expected_version=version,
                    delegate_role=person["role"], delegate_id=person["id"], expected_result=expected,
                    due_at=due.isoformat() if due else None, command_id=command_id)
                _saved(key, "Mission confiée. La prise en charge reste à confirmer.", event_id)

        elif mode in ("accept", "refuse", "submit"):
            title, decision = {"accept": ("Accepter la mission", "ACCEPT"), "refuse": ("Je ne peux pas prendre cette mission", "REFUSE"),
                               "submit": ("Prêt à valider", "SUBMIT")}[mode]
            st.subheader(title)
            with st.form(f"{widget}_form", clear_on_submit=False):
                comment = st.text_area("Motif de l’impossibilité" if mode == "refuse" else "Travail réalisé et résultat à valider" if mode == "submit" else "Commentaire (facultatif)", key=f"{widget}_comment")
                submitted = st.form_submit_button("Transmettre pour validation" if mode == "submit" else title, type="primary")
            if submitted:
                quality.respond_assignment(engine, actor, event_id, expected_version=version, decision=decision,
                                           comment=comment, command_id=command_id)
                _saved(key, "Votre réponse est enregistrée et transmise au responsable du suivi.", event_id)

        elif mode == "step":
            st.subheader("Ajouter une étape facultative")
            with st.form(f"{widget}_form", clear_on_submit=False):
                title = st.text_input("Ce qu’il faut faire", key=f"{widget}_title")
                description = st.text_area("Contexte utile (facultatif)", key=f"{widget}_description")
                st.caption("Cette étape reste dans la même action et pourra être traitée dans la fenêtre Clôturer.")
                submitted = st.form_submit_button("Ajouter l’étape", type="primary")
            if submitted:
                quality.add_step(engine, actor, event_id, title, expected_version=version, description=description)
                _saved(key, "Étape ajoutée à cette action.", event_id)

        elif mode == "attachment":
            st.subheader("Joindre un document")
            with st.form(f"{widget}_form", clear_on_submit=False):
                upload_options = {"type": ["pdf", "docx", "xlsx", "txt", "csv", "png", "jpg", "jpeg"], "key": f"{widget}_upload"}
                if "max_upload_size" in inspect.signature(st.file_uploader).parameters:
                    upload_options["max_upload_size"] = 10
                upload = st.file_uploader("Document (10 Mo maximum)", **upload_options)
                choices = {"PUBLIC": "Communicable au demandeur et aux personnes habilitées"}
                if permissions.get("internal"):
                    choices = {"INTERNAL": "Interne uniquement", **choices}
                audience = st.selectbox("Partage de cette pièce", list(choices), format_func=choices.get, key=f"{widget}_audience")
                st.caption("Une nouvelle pièce est conservée avec son empreinte. Son partage ne donne aucun droit sur les autres documents.")
                submitted = st.form_submit_button("Joindre le document", type="primary")
            if submitted:
                if upload is None:
                    raise ValueError("Choisissez un document à joindre.")
                if upload.size > 10 * 1024 * 1024:
                    raise ValueError("Le document dépasse la limite de 10 Mo. Aucune pièce n’a été ajoutée.")
                quality.add_attachment(engine, actor, event_id, expected_version=version, data=upload.getvalue(),
                    filename=upload.name, audience=audience, command_id=command_id)
                _saved(key, "Document joint avec le partage indiqué.", event_id)

        elif mode == "delete":
            st.subheader(f"Suppression unitaire de {event['public_id']}")
            preview = quality.deletion_preview(engine, actor, event_id)
            st.write(preview.get("message") or "La formation, les identités et les pièces partagées seront conservées.")
            if preview.get("blocked") or not preview.get("allowed", True):
                st.warning(" · ".join(preview.get("blockers", [])) or preview.get("reason") or "La politique de conservation ne permet pas cette suppression.")
                return
            counts = preview.get("counts") or preview.get("categories") or {}
            if counts:
                labels = {"quality_event_messages": "Messages", "quality_event_history": "Historique détaillé",
                          "quality_event_actions": "Étapes", "quality_attachments": "Pièces propres à l’action",
                          "quality_notification_outbox": "Notifications associées"}
                st.dataframe(pd.DataFrame([{"Élément": labels.get(kind, str(kind)), "Nombre": count} for kind, count in counts.items()]), hide_index=True, use_container_width=True)
            with st.form(f"{widget}_form", clear_on_submit=False):
                reason = st.text_area("Motif de suppression", key=f"{widget}_reason")
                confirmed = st.checkbox("J’ai vérifié cet aperçu et confirme la suppression de cette seule action Qualité", key=f"{widget}_confirmed")
                submitted = st.form_submit_button("Supprimer cette action Qualité")
            if submitted:
                if not confirmed:
                    raise ValueError("Confirmez la suppression unitaire après avoir vérifié l’aperçu.")
                quality.delete_action(engine, actor, event_id, expected_version=version, reason=reason, command_id=command_id)
                st.session_state.pop(f"{key}_selected", None)
                _saved(key, "Action Qualité supprimée selon la politique applicable. Le reçu minimal est conservé.")
    except Exception as exc:
        _error(exc)
    if st.button("Fermer cette fenêtre", key=f"{widget}_dismiss"):
        _dismiss_dialog()
        st.rerun()


def render_quality_detail(engine, actor, event_id, *, key="detail"):
    """The same detail and single closure dialog in every authorized space."""
    case = quality.get_action(engine, actor, event_id)
    event = case["event"]
    rights = case["permissions"]
    st.markdown(f"### {event['public_id']} — {event.get('subject') or ''}")
    st.caption(f"{STATUS_LABELS.get(event['status'], event['status'])} · {event.get('action_no') or 'Générale / sans formation'} · Ouverture {_date_label(event.get('created_at'))}")
    if event.get("data_classification") == "TEST":
        st.info("TEST — cette action est exclue des statistiques réelles.")
    if event.get("sensitivity") == "RESTRICTED":
        st.caption("Accès restreint aux personnes expressément habilitées.")
    st.write(event.get("description") or "")
    c1, c2, c3 = st.columns(3)
    c1.write(f"**Responsable :** {event.get('owner_name') or 'À attribuer'}")
    c2.write(f"**Échéance :** {_date_label(event.get('due_at'))}")
    c3.write(f"**Nature :** {NATURE_LABELS.get(event.get('action_nature'), '—')}")
    if event.get("expected_result"):
        st.write(f"**Résultat attendu :** {event['expected_result']}")
    if event.get("closure_comment"):
        st.write(f"**Bilan conservé :** {event['closure_comment']}")
    if actor.role == "ADMIN" and event.get("origin") == "VEILLE":
        from quality_watch import list_decisions
        linked = [row for row in list_decisions(engine, actor) if row.get("action_id") == int(event_id)]
        if linked:
            with st.expander("Source de veille à l’origine de cette action"):
                source = linked[-1]
                st.write(source.get("title") or "Information de veille")
                st.caption(f"Publication : {_date_label(source.get('published_at'))} · Effet annoncé : {_date_label(source.get('effective_at'))}")
                if str(source.get("url") or "").startswith("https://"):
                    st.link_button("Consulter la source originale", source["url"])
    buttons = []
    if rights.get("update") or rights.get("respond"):
        buttons.append(("Mettre à jour" if actor.role in ("ADMIN", "TRAINER") else "Répondre", "update", False))
    if rights.get("assign") and event["status"] not in CLOSED:
        buttons.append(("Confier", "assign", False))
    if rights.get("close") and event["status"] not in CLOSED:
        buttons.append(("Clôturer", "close", True))
    elif rights.get("reopen") and event["status"] in CLOSED:
        buttons.append(("Rouvrir", "reopen", True))
    own_assignment = (str(event.get("assigned_id")) == str(actor.subject_id) and event.get("assigned_role") == actor.role)
    if own_assignment and event["status"] not in CLOSED:
        assignment = event.get("delegation_status")
        if assignment in ("PENDING", "PROPOSED", "PROPOSEE", "ASSIGNED"):
            st.info("Mission confiée — votre prise en charge est attendue.")
            buttons.extend([("Accepter", "accept", False), ("Je ne peux pas", "refuse", False)])
        elif assignment in ("ACCEPTED", "ACCEPTEE", "IN_PROGRESS"):
            buttons.append(("Prêt à valider", "submit", True))
    # Two columns keep the primary commands legible in small viewports.
    for start in range(0, len(buttons), 2):
        columns = st.columns(2)
        for column, (label, mode, primary) in zip(columns, buttons[start:start + 2]):
            if column.button(label, key=f"{key}_{mode}_{event_id}", type="primary" if primary else "secondary", use_container_width=True):
                _open_dialog(engine, actor, key, mode, event_id)
    with st.expander("Étapes et pièces associées", expanded=False):
        steps = case.get("steps", [])
        if steps:
            for step in steps:
                label = {"A_FAIRE": "À faire", "EN_COURS": "En cours", "EN_ATTENTE": "En attente", "A_VERIFIER": "À vérifier", "TERMINEE": "Terminée", "ANNULEE": "Abandonnée"}.get(step.get("status"), step.get("status") or "—")
                st.write(f"**{step.get('title') or 'Étape'}** · {label}")
                if step.get("effectiveness_result"):
                    st.caption(step["effectiveness_result"])
        if rights.get("add_step") and event["status"] not in CLOSED:
            if st.button("Ajouter une étape (facultatif)", key=f"{key}_step_{event_id}"):
                _open_dialog(engine, actor, key, "step", event_id)
        for attachment in case.get("attachments", []):
            try:
                document = quality.read_attachment(engine, actor, event_id, attachment["id"])
                st.download_button(f"Télécharger {document['filename']}", document["data"], file_name=document["filename"],
                    mime=document.get("mime_type") or "application/octet-stream", key=f"{key}_file_{event_id}_{attachment['id']}")
            except Exception as exc:
                _error(exc)
        if rights.get("upload"):
            if st.button("Joindre un document", key=f"{key}_attachment_{event_id}"):
                _open_dialog(engine, actor, key, "attachment", event_id)
    with st.expander("Avancées, réponses et historique", expanded=True):
        messages = case.get("messages", [])
        if not messages:
            st.caption("Aucune avancée ajoutée pour le moment.")
        for message in messages:
            audience = " · Note interne" if message.get("audience") == "INTERNAL" or message.get("direction") == "INTERNE" else ""
            st.caption(f"{_timestamp(engine, actor, message.get('created_at'), event.get('action_id'))} · {message.get('author') or message.get('actor') or 'Auteur enregistré'}{audience}")
            st.write(message.get("message") or "")
        history = case.get("history", [])
        if history:
            with st.expander("Décisions et changements réels"):
                for item in history:
                    st.caption(f"{_timestamp(engine, actor, item.get('created_at'), event.get('action_id'))} · {item.get('actor') or 'Auteur enregistré'} · {item.get('change_kind') or item.get('event_type') or 'Changement'}")
                    # The service already projects the allowed event data. Use a
                    # structured renderer, never unsafe HTML for user content.
                    if item.get("summary"):
                        st.write(item["summary"])
                    elif item.get("after_json"):
                        import json
                        try:
                            fields = json.loads(item["after_json"])
                            if isinstance(fields, dict):
                                labels = {"status": "Statut", "closure_comment": "Bilan", "reason": "Motif",
                                          "description": "Contexte", "subject": "Objet", "expected_result": "Résultat attendu",
                                          "due_at": "Échéance", "delegation_status": "Prise en charge",
                                          "action_nature": "Nature", "data_classification": "Données",
                                          "summary": "Bilan", "comment": "Avancée", "public_id": "Référence"}
                                for field, label in labels.items():
                                    if field in fields and fields[field] not in (None, ""):
                                        value = fields[field]
                                        if field == "status": value = STATUS_LABELS.get(value, value)
                                        if field == "action_nature": value = NATURE_LABELS.get(value, value)
                                        if field == "due_at": value = _date_label(value)
                                        if field == "delegation_status": value = {"PENDING": "Attendue", "ACCEPTED": "Acceptée", "REFUSED": "Refusée", "SUBMITTED": "Prête à valider"}.get(value, value)
                                        st.write(f"**{label} :** {value}")
                        except (ValueError, TypeError):
                            st.caption("Détail historique conservé.")
    if actor.role == "ADMIN":
        with st.expander("Administration de cette action"):
            _render_quality_access(engine, actor, event, key)
            with st.expander("État des notifications par courriel"):
                deliveries = quality.delivery_status(engine, actor, event_id)
                st.caption("Accepté signifie que le serveur de messagerie a accepté le courriel ; cela ne prouve ni sa remise finale ni sa lecture. Un résultat inconnu nécessite une vérification avant tout renvoi.")
                if deliveries:
                    statuses = {"PENDING": "En attente", "ACCEPTED": "Accepté par le serveur", "RETRY": "Nouvel essai prévu",
                                "UNKNOWN": "Résultat inconnu — à vérifier", "SENDING": "Envoi engagé", "CANCELLED": "Annulé",
                                "SUPPRESSED": "Non envoyé selon les paramètres", "FAILED": "Échec"}
                    st.dataframe(pd.DataFrame([{"Destinataire": f"{row['recipient_role']} · {row['recipient_id']}",
                        "État": statuses.get(row["status"], row["status"]), "Tentatives": row.get("attempts") or 0,
                        "Accepté le": _timestamp(engine, actor, row.get("accepted_at")),
                        "Dernière information": row.get("last_error") or "—"} for row in deliveries]), hide_index=True, use_container_width=True)
                else:
                    st.caption("Aucun courriel en attente ou enregistré pour cette action. Les notifications dans les espaces personnels restent distinctes des courriels.")
            if rights.get("delete") and st.button("Examiner la suppression unitaire", key=f"{key}_delete_{event_id}"):
                _open_dialog(engine, actor, key, "delete", event_id)


def _render_quality_access(engine, actor, event, key):
    """Narrow named grants, using existing identities and no organization tree."""
    event_id = event["id"]
    people = {(row["role"], str(row["id"])): row for row in quality.eligible_referents(engine, actor, event_id)}
    grants = {(row["role"], str(row["subject_id"])): row for row in quality.access_grants(engine, actor, event_id)}
    if grants:
        st.dataframe(pd.DataFrame([{"Personne": people.get(identity, {}).get("label") or f"{identity[0]} · {identity[1]}",
            "Compte actif": bool(grant.get("account_active")), "Accès nominatif": "Révoqué" if grant.get("revoked_at") else "Lecture",
            "Notes internes": bool(grant.get("can_internal")), "Validation": bool(grant.get("can_validate"))}
            for identity, grant in grants.items()]), hide_index=True, use_container_width=True)
    options = dict(people)
    for identity, grant in grants.items():
        if not grant.get("revoked_at"):
            options.setdefault(identity, {"label": f"{identity[0]} · {identity[1]} — compte inactif, retrait possible"})
    chosen = st.selectbox("Référent habilité pour cette action", [None] + list(options),
        format_func=lambda value: "Choisir une personne existante" if value is None else options[value]["label"], key=f"{key}_referent_{event_id}")
    st.caption("Accès à cette action uniquement : lecture, notes internes ou validation selon le besoin. Aucun nouveau compte ni niveau d’administration n’est créé.")
    if chosen is None:
        return
    grant = grants.get(chosen) or {}
    identity_key = uuid.uuid5(uuid.NAMESPACE_OID, repr(chosen)).hex[:16]
    prefix = f"{key}_grant_{event_id}_{identity_key}"
    current = {"row_version": event["row_version"], "internal": bool(grant.get("can_internal")),
               "validate": bool(grant.get("can_validate")), "revoke": bool(grant.get("revoked_at"))}
    values = lambda row: {field: bool(row.get(field)) for field in ("internal", "validate", "revoke")}
    snapshot = _configuration_snapshot(current, prefix, values, "Les habilitations de cette action")
    with st.form(f"{prefix}_form", clear_on_submit=False):
        internal = st.checkbox("Autoriser la lecture des notes internes", value=snapshot["internal"], key=f"{prefix}_internal")
        validate = st.checkbox("Autoriser la validation et la clôture de cette action", value=snapshot["validate"], key=f"{prefix}_validate")
        revoke = st.checkbox("Révoquer cet accès nominatif", value=snapshot["revoke"], key=f"{prefix}_revoke")
        if chosen not in people:
            st.caption("Ce compte est inactif : son accès peut uniquement être révoqué.")
        save = st.form_submit_button("Enregistrer cette habilitation")
    if save:
        try:
            changed = quality.set_access_grant(engine, actor, event_id, expected_version=snapshot["row_version"],
                role=chosen[0], subject_id=chosen[1], can_internal=internal, can_validate=validate, revoke=revoke)
            st.session_state.pop(f"{prefix}_snapshot", None)
            _saved(key, "Habilitation enregistrée." if changed else "Aucun changement d’habilitation.", event_id)
        except Exception as exc:
            _error(exc)


def render_quality_plan(engine, actor, *, action_id=None, key="plan", status=None,
                        prestation_type=None, focus_event_id=None, create=True):
    key = _key(actor, key)
    quality.require_actor(engine, actor)
    if f"{key}_flash" in st.session_state:
        st.success(st.session_state.pop(f"{key}_flash"))
    title = "Plan d’actions unique" if actor.role in ("ADMIN", "TRAINER") else "Mes demandes"
    st.markdown(f"### {title}")
    if create:
        if st.button("Nouvelle action" if actor.role in ("ADMIN", "TRAINER") else "Nouvelle demande", type="primary", key=f"{key}_new"):
            _open_dialog(engine, actor, key, "create")
    st.caption("Créer, suivre / confier, clôturer. Les actions générales sans formation restent dans ce plan.")
    search = st.text_input("Rechercher dans les actions accessibles", key=f"{key}_search")
    statuses = {None: "Tous les statuts", "OPEN": "Actions ouvertes", "OVERDUE": "En retard", **STATUS_LABELS}
    values = list(statuses)
    c1, c2 = st.columns(2)
    selected_status = c1.selectbox("Statut du plan", values, index=values.index(status) if status in values else 0,
                                   format_func=statuses.get, key=f"{key}_status")
    classifications = {None: "Toutes (TEST / RÉEL / à examiner)", "REAL": "RÉEL uniquement", "TEST": "TEST uniquement", "A_EXAMINER": "À examiner"}
    classification = c2.selectbox("Données du plan", list(classifications), format_func=classifications.get, key=f"{key}_classification")
    filters = {"action_id": action_id, "status": selected_status, "classification": classification,
               "search": search, "prestation_type": prestation_type}
    visible_responsibles = {}
    for row in quality.list_actions(engine, actor, action_id=action_id, classification=classification, prestation_type=prestation_type):
        if row.get("assigned_id"):
            visible_responsibles[str(row["assigned_id"])] = row.get("owner_name") or "Responsable enregistré"
    with st.expander("Autres filtres"):
        c1, c2 = st.columns(2)
        origin = c1.selectbox("Origine", [None] + list(ORIGIN_LABELS),
            format_func=lambda value: "Toutes les origines" if value is None else ORIGIN_LABELS[value], key=f"{key}_origin")
        nature = c2.selectbox("Nature", [None] + list(NATURE_LABELS),
            format_func=lambda value: "Toutes les natures" if value is None else NATURE_LABELS[value], key=f"{key}_nature")
        mine = st.checkbox("Mes actions confiées", key=f"{key}_mine") if actor.role in ("ADMIN", "TRAINER") else False
        responsible = st.selectbox("Responsable", [None] + list(visible_responsibles),
            format_func=lambda value: "Tous les responsables" if value is None else visible_responsibles[value], key=f"{key}_responsible")
        due_before = st.date_input("Échéance au plus tard (facultatif)", value=None, format=DATE_FORMAT, key=f"{key}_before")
        filters.update(origin=origin, nature=nature, mine=mine, assigned_id=responsible,
                       due_before=due_before.isoformat() if due_before else None)
    rows = quality.list_actions(engine, actor, **filters)
    counts = quality.plan_counts(engine, actor, **filters)
    for group in [[("Actions", "total"), ("Ouvertes", "open"), ("À attribuer", "unassigned")],
                  [("À valider", "to_validate"), ("Clôturées", "closed"), ("En retard", "overdue")]]:
        for column, (label, field) in zip(st.columns(3), group):
            column.metric(label, counts.get(field, 0))
    if rows:
        st.dataframe(pd.DataFrame([{
            "Référence": row["public_id"], "Ouverture": _date_label(row.get("created_at")),
            "Action à réaliser": row.get("subject") or "", "Contexte": row.get("action_no") or "Générale",
            "Origine": ORIGIN_LABELS.get(row.get("origin"), row.get("origin") or "—"),
            "Nature": NATURE_LABELS.get(row.get("action_nature"), "—"),
            "Responsable": row.get("owner_name") or "À attribuer",
            "Statut": STATUS_LABELS.get(row.get("status"), row.get("status")),
            "Échéance": _date_label(row.get("due_at")), "Dernière avancée": _date_label(row.get("updated_at")),
            "Données": "RÉEL" if row.get("data_classification") == "REAL" else row.get("data_classification") or "À examiner",
        } for row in rows]), use_container_width=True, hide_index=True)
        with st.expander("Exporter ce périmètre"):
            st.caption("La date, les filtres et l’inclusion éventuelle des essais figurent dans l’export. Les droits sont identiques à ceux du plan.")
            st.download_button("Export tabulaire (CSV)", quality.export_plan_csv(engine, actor, **filters),
                file_name="plan_actions_qualite.csv", mime="text/csv", key=f"{key}_csv")
            st.download_button("Synthèse PDF", quality.export_plan_pdf(engine, actor, **filters),
                file_name="plan_actions_qualite.pdf", mime="application/pdf", key=f"{key}_pdf")
        choices = {int(row["id"]): row for row in rows}
        selected_key = f"{key}_selected"
        pending_selection = st.session_state.pop(f"{key}_next_selected", None)
        if pending_selection in choices:
            st.session_state[selected_key] = pending_selection
        if focus_event_id is not None:
            # Direct notification access is revalidated by the service below.
            quality.get_action(engine, actor, focus_event_id)
            if int(focus_event_id) in choices:
                st.session_state[selected_key] = int(focus_event_id)
        if st.session_state.get(selected_key) not in choices:
            st.session_state[selected_key] = next(iter(choices))
        selected_id = st.selectbox("Ouvrir une action", list(choices), key=selected_key,
            format_func=lambda value: f"{choices[value]['public_id']} — {choices[value].get('subject') or ''}")
        render_quality_detail(engine, actor, selected_id, key=key)
    else:
        st.info("Aucune action dans ce périmètre.")
    dialog = st.session_state.get(f"{key}_dialog", {})
    if dialog and (_HAS_DISMISS_CALLBACK or dialog.pop("show", False)):
        _action_dialog(engine, actor, key, action_id=action_id)


def render_quality_legacy(engine, actor, *, key="legacy"):
    quality.require_admin(engine, actor)
    key = _key(actor, key)
    with st.expander("Reprise des anciennes demandes et actions"):
        st.caption("Rapprochement par les liens d’origine, jamais par ressemblance de titre. Auteurs, réponses et anciennes références sont conservés ; les cas ambigus restent à examiner.")
        if st.button("Intégrer les références historiques de cet organisme", key=f"{key}_adopt"):
            try:
                st.session_state[f"{key}_result"] = quality.migrate_legacy(engine, actor)
                st.success("Reprise historique terminée pour les liens vérifiables. La relancer ne crée pas de doublons.")
            except Exception as exc:
                _error(exc)
        result = st.session_state.get(f"{key}_result")
        if not result:
            return
        st.write(f"{result.get('events_adopted', 0)} fiche(s) conservée(s) · "
                 f"{result.get('sources_created', 0)} demande(s) reprise(s) · "
                 f"{result.get('steps_created', 0)} étape(s) rattachée(s) · "
                 f"{result.get('already_mapped', 0)} correspondance(s) déjà établies.")
        unresolved = result.get("unresolved") or []
        if not unresolved:
            st.caption("Aucune correspondance en attente dans ce contrôle.")
            return
        kinds = {"TRAINER_REPORT": "Demande intervenant", "BENEFICIARY_REPORT": "Demande bénéficiaire",
                 "QUALITY_ISSUE": "Affaire Qualité", "IMPROVEMENT_ACTION": "Ancienne mesure", "QUALITY_EVENT": "Fiche Qualité existante"}
        label = lambda row: f"{kinds.get(row['kind'], row['kind'])} #{row['source_id']}"
        st.dataframe(pd.DataFrame([{"Source historique": label(row), "À vérifier": row["reason"]}
            for row in unresolved]), hide_index=True, use_container_width=True)
        general = {(row["kind"], int(row["source_id"])): row for row in unresolved
                   if "Organisme non renseigné" in row.get("reason", "")}
        if general:
            organizations = quality.available_organizations(engine, actor.role, actor.subject_id)
            organization = next((row["name"] for row in organizations if int(row["id"]) == actor.organization_id), "cet organisme")
            selected = st.multiselect("Anciennes sources à affecter à cet organisme", list(general),
                default=[], format_func=lambda value: label(general[value]), key=f"{key}_general")
            st.caption("Sélectionnez seulement les sources dont vous avez vérifié l’organisme d’origine. Aucun choix n’est présélectionné.")
            if st.button(f"Affecter au contexte {organization}", disabled=not selected, key=f"{key}_assign_general"):
                try:
                    st.session_state[f"{key}_result"] = quality.migrate_legacy(engine, actor, general_source_ids=selected)
                    st.rerun()
                except Exception as exc:
                    _error(exc)
        candidates = {(row["kind"], int(row["source_id"])): row for row in unresolved if row.get("candidate_ids")}
        if candidates:
            chosen = st.selectbox("Source historique à rapprocher", [None] + list(candidates),
                format_func=lambda value: "Choisir une source" if value is None else label(candidates[value]), key=f"{key}_ambiguous")
            if chosen is not None:
                # Candidate IDs are suggestions only: read permission and the
                # strict historical identity/link rules are rechecked server-side.
                authorized = {}
                for event_id in candidates[chosen]["candidate_ids"]:
                    try:
                        authorized[event_id] = quality.get_action(engine, actor, event_id)["event"]
                    except (ValueError, PermissionError):
                        continue
                target = st.selectbox("Action existante correspondant à cette source", [None] + list(authorized),
                    format_func=lambda value: "Choisir après vérification" if value is None else
                        f"{authorized[value]['public_id']} — {authorized[value].get('subject') or ''}", key=f"{key}_target_{chosen}")
                if target is not None:
                    st.write(authorized[target].get("description") or "Aucun contexte renseigné.")
                    version_key = f"{key}_legacy_version_{chosen}_{target}"
                    if version_key not in st.session_state:
                        st.session_state[version_key] = authorized[target]["row_version"]
                    if st.button("Confirmer cette correspondance historique", key=f"{key}_reconcile"):
                        try:
                            quality.reconcile_legacy_source(engine, actor, target, chosen[0], chosen[1],
                                expected_version=st.session_state[version_key])
                            st.session_state[f"{key}_result"] = quality.migrate_legacy(engine, actor)
                            st.session_state.pop(version_key, None)
                            st.rerun()
                        except Exception as exc:
                            _error(exc)
                    if authorized[target]["row_version"] != st.session_state.get(version_key):
                        st.warning("L’action a changé. Relisez sa correspondance avant de confirmer.")
                        if st.button("Relire la correspondance actualisée", key=f"{key}_reread_legacy"):
                            st.session_state[version_key] = authorized[target]["row_version"]
                            st.rerun()


def render_quality_satisfaction(engine, actor, *, action_id=None, prestation_type=None,
                                key="satisfaction", detailed=True):
    """Method-versioned, finalized questionnaires; HOT and COLD never mixed."""
    from quality_metrics import survey_dashboard, export_survey_csv
    key = _key(actor, key)
    quality.require_admin(engine, actor)
    period = {}
    if detailed:
        with st.expander("Période des résultats"):
            c1, c2 = st.columns(2)
            beginning = c1.date_input("À partir du", value=None, format=DATE_FORMAT, key=f"{key}_from")
            end = c2.date_input("Jusqu’au", value=None, format=DATE_FORMAT, key=f"{key}_to")
            period = {"date_from": beginning.isoformat() if beginning else None,
                      "date_to": end.isoformat() if end else None}
    filters = {"action_id": action_id, "prestation_type": prestation_type,
               "classification": "REAL", **period}
    try:
        data = survey_dashboard(engine, actor, **filters)
    except Exception as exc:
        _error(exc)
        return
    st.markdown("### Satisfaction à chaud et à froid")
    labels = {"HOT": "À chaud", "COLD": "À froid", "TRAINER": "Intervenant", "CLIENT": "Client / entreprise",
              "PRESCRIBER": "Prescripteur", "OPCO": "Financeur / OPCO"}

    def card(column, kind):
        item = data.get("by_kind", {}).get(kind, {})
        score = item.get("score")
        rate = item.get("satisfaction_rate")
        returned = item.get("return_rate")
        column.metric(labels.get(kind, kind), "Non disponible" if score is None else f"{score:.2f}/5".replace(".", ","))
        column.write("**Satisfaction :** " + ("aucune note globale exploitable" if rate is None else f"{rate:.1f} %".replace(".", ",")))
        column.write("**Retour des questionnaires :** " + ("aucun envoi retenu" if returned is None else f"{returned:.1f} %".replace(".", ",")))
        column.caption(f"{item.get('n_global', 0)} note(s) globale(s) valide(s) · {item.get('completed', 0)} questionnaire(s) finalisé(s) · {item.get('sent', 0)} invitation(s) effectivement envoyée(s).")
        if item.get("planned"):
            column.caption(f"{item['planned']} questionnaire(s) prévu(s), exclus du dénominateur des retours.")

    for column, kind in zip(st.columns(2), ("HOT", "COLD")):
        card(column, kind)
    if detailed:
        with st.expander("Autres familles de questionnaires"):
            for group in (("TRAINER", "CLIENT"), ("PRESCRIBER", "OPCO")):
                for column, kind in zip(st.columns(2), group):
                    card(column, kind)
        with st.expander("Méthode de calcul et périmètre"):
            st.write(data.get("method") or "Une note globale valide par questionnaire finalisé ; les familles, NPS, réponses vides et essais sont séparés.")
            st.caption(f"Méthode {data.get('method_version') or 'non disponible'} · TEST exclus · Calcul {_timestamp(engine, actor, data.get('generated_at'), action_id)}")
            if data.get("scope"):
                st.write(data["scope"])
            if data.get("anomalies"):
                st.warning("Des réponses ou campagnes ont été exclues du calcul ; consultez le détail ci-dessous.")
                st.write(data["anomalies"])
            st.download_button("Exporter ces résultats (CSV)", export_survey_csv(engine, actor, **filters),
                file_name="resultats_qualite.csv", mime="text/csv", key=f"{key}_export")
        themes = data.get("themes", [])
        st.markdown("#### Moyennes par thème")
        if themes:
            st.dataframe(pd.DataFrame([{"Famille": labels.get(row.get("kind"), row.get("kind")),
                "Thème": row.get("label") or row.get("rubric_code"), "Version du modèle": row.get("template_version"),
                "Questionnaires": row.get("questionnaires"), "Items": row.get("items"), "Moyenne /5": row.get("mean")}
                for row in themes]), use_container_width=True, hide_index=True)
        else:
            st.caption("Aucune réponse exploitable dans ce périmètre. Les moyennes ne sont pas remplacées par zéro.")


def render_quality_settings(engine, actor, *, action_id=None, key="settings"):
    """Explicit organization settings, outside the ordinary action workflow."""
    from db import one
    from quality_metrics import (metric_policy, configure_metric_policy,
                                 publish_client_satisfaction, revoke_client_satisfaction)
    quality.require_admin(engine, actor)
    key = _key(actor, key)
    with st.expander("Méthode des indicateurs et publication Client"):
        policy = metric_policy(engine, actor)
        with st.form(f"{key}_metric_policy", clear_on_submit=False):
            positive = st.number_input("Note globale positive à partir de", min_value=1, max_value=5,
                value=int(policy.get("positive_min") or 4), step=1)
            distinct = st.number_input("Minimum de répondants distincts pour une publication", min_value=5,
                value=max(5, int(policy.get("min_distinct") or 5)), step=1)
            enabled = st.checkbox("Autoriser des publications Client après vérification", value=bool(policy.get("client_enabled")))
            confirmed = st.checkbox("Je confirme cette méthode et ce seuil pour mon organisme", value=False)
            st.caption("Aucune satisfaction individuelle n’est publiée. Le seuil s’ajoute à la protection des petits groupes complémentaires ; le calendrier garde ses propres droits.")
            submitted = st.form_submit_button("Enregistrer la méthode")
        if submitted:
            try:
                configure_metric_policy(engine, actor, positive_min=int(positive), min_distinct=int(distinct),
                                        client_enabled=enabled, confirmed=confirmed)
                st.success("Méthode enregistrée avec son état de confirmation.")
            except Exception as exc:
                _error(exc)
        if action_id is not None:
            with st.form(f"{key}_publish_{action_id}", clear_on_submit=False):
                family = st.selectbox("Famille à publier", ["HOT", "COLD"],
                    format_func=lambda value: "À chaud" if value == "HOT" else "À froid")
                reviewed = st.checkbox("J’ai vérifié cet agrégat de formation et son caractère communicable")
                st.caption("La publication porte sur une formation clôturée et une famille fixe. Les réponses identifiables, bilans et sous-groupes insuffisants restent protégés.")
                publish = st.form_submit_button("Publier cet agrégat aux clients habilités")
                revoke = st.form_submit_button("Retirer cette publication Client")
            try:
                if publish:
                    publish_client_satisfaction(engine, actor, action_id, campaign_kind=family, confirmed=reviewed)
                    st.success("Agrégat fixe publié pour les seuls contacts autorisés sur cette formation.")
                if revoke:
                    revoke_client_satisfaction(engine, actor, action_id, campaign_kind=family)
                    st.success("Publication retirée des espaces Client.")
            except Exception as exc:
                _error(exc)
    with st.expander("Notifications, rappels et conservation Qualité"):
        current = one(engine, "SELECT * FROM quality_organization_settings WHERE organization_id=:o",
                      {"o": actor.organization_id}) or {}
        with st.form(f"{key}_organization", clear_on_submit=False):
            email = st.checkbox("Utiliser le canal email Qualité en complément des notifications internes", value=bool(current.get("email_enabled")))
            delay = st.number_input("Rappel après échéance (jours calendaires)", min_value=0, max_value=365,
                value=int(current.get("reminder_days") or 0), step=1)
            retention = st.number_input("Conservation minimale avant suppression unitaire (jours)", min_value=0, max_value=36500,
                value=int(current["retention_days"]) if current.get("retention_days") is not None else None, step=1)
            deletion = st.checkbox("Autoriser la suppression unitaire administrative après contrôle de conservation", value=bool(current.get("deletion_enabled")))
            st.caption("Sans politique renseignée, la suppression reste bloquée. Une conservation propre à une action peut imposer un délai plus long. Aucun nettoyage groupé n’est effectué ici.")
            save = st.form_submit_button("Enregistrer ces paramètres Qualité")
        if save:
            try:
                quality.configure_organization(engine, actor, deletion_enabled=deletion,
                    retention_days=int(retention) if retention is not None else None,
                    email_enabled=email, reminder_days=int(delay))
                st.success("Paramètres Qualité enregistrés.")
            except Exception as exc:
                _error(exc)


def render_watch_decisions(engine, actor, *, key="decisions", search=""):
    """Human no-action decisions are visible alongside, never counted as work."""
    if actor.role != "ADMIN":
        return
    from quality_watch import list_decisions
    decisions = [row for row in list_decisions(engine, actor) if row.get("decision") == "NO_ACTION"]
    if search:
        needle = search.casefold()
        decisions = [row for row in decisions if needle in str(row.get("title", "")).casefold() or needle in str(row.get("reason", "")).casefold()]
    with st.expander(f"Décisions de veille sans action ({len(decisions)})"):
        st.caption("Décisions closes et motivées. Elles ne constituent pas des tâches réalisées et n’augmentent pas les compteurs du plan.")
        if decisions:
            st.dataframe(pd.DataFrame([{"Information": row.get("title") or f"Information #{row.get('item_id')}",
                "Motif": row.get("reason") or "", "Date": _timestamp(engine, actor, row.get("created_at") or row.get("decided_at")),
                "Décision": "Sans action nécessaire"} for row in decisions]), hide_index=True, use_container_width=True)
        else:
            st.caption("Aucune décision sans action dans ce périmètre.")


def _configuration_snapshot(current, key, values, label):
    """Keep the read version and entered values until an explicit reread.

    Configuration forms use the same optimistic-concurrency discipline as an
    action dialog. Every widget has a stable key; a concurrent save never
    silently replaces its inputs or advances the version sent to the service.
    """
    snapshot_key = f"{key}_snapshot"
    if snapshot_key not in st.session_state:
        st.session_state[snapshot_key] = deepcopy(current)
    previous = st.session_state[snapshot_key]
    if current.get("row_version") != previous.get("row_version"):
        st.warning(f"{label} a changé pendant votre saisie. Votre brouillon est conservé ; relisez la configuration avant de l’enregistrer.")
        if st.button(f"Relire : {label}", key=f"{key}_reread"):
            old_values, new_values = values(previous), values(current)
            for field, old_value in old_values.items():
                widget_key = f"{key}_{field}"
                if widget_key in st.session_state and st.session_state[widget_key] == old_value:
                    st.session_state[widget_key] = new_values[field]
            st.session_state[snapshot_key] = deepcopy(current)
            previous = st.session_state[snapshot_key]
            st.info("Configuration actualisée relue. Les valeurs que vous aviez modifiées sont conservées.")
    return previous


def render_quality_watch(engine, actor, *, key="watch"):
    """Selective watch, its human decisions and source-specific success cursors."""
    import json
    import quality_watch as watch
    quality.require_admin(engine, actor)
    key = _key(actor, key)
    if st.session_state.get(f"{key}_flash"):
        st.success(st.session_state.pop(f"{key}_flash"))
    st.markdown("### Veille utile à mon organisme")
    st.caption("Sélectionnez les sources pertinentes. Chaque information peut produire une action dans le plan unique ou une décision motivée sans action.")
    try:
        sources = watch.list_sources(engine, actor)
        by_id = {row["id"]: row for row in sources}
        source_id = st.selectbox("Source à consulter", [None] + list(by_id),
            format_func=lambda value: "Toutes les sources" if value is None else by_id[value]["name"], key=f"{key}_source")
        decision = st.selectbox("Traitement des informations", [None, "A_EXAMINER", "ACTION", "NO_ACTION"],
            format_func=lambda value: {None: "Tous", "A_EXAMINER": "À examiner", "ACTION": "Action ouverte", "NO_ACTION": "Sans action nécessaire"}[value], key=f"{key}_decision")
        items = watch.list_items(engine, actor, source_id=source_id, decision=decision)
        if items:
            mapping = {row["id"]: row for row in items}
            chosen = st.selectbox("Information à examiner", list(mapping),
                format_func=lambda value: mapping[value].get("title") or f"Information #{value}", key=f"{key}_item")
            item = mapping[chosen]
            st.markdown(f"#### {item.get('title') or 'Information de veille'}")
            st.write(item.get("summary") or "Résumé non renseigné ; consulter la source.")
            priority_labels = {"LOW": "Faible", "NORMAL": "Normale", "HIGH": "Haute", "CRITICAL": "Critique"}
            st.caption(f"Source : {item.get('source_name') or '—'} · Priorité : {priority_labels.get(item.get('priority'), 'À préciser')}")
            if item.get("scope"):
                st.write(f"**Périmètre de la source :** {item['scope']}")
            st.caption(f"Publication : {_date_label(item.get('published_at'))} · Effet annoncé : {_date_label(item.get('effective_at'))}")
            if item.get("url") and str(item["url"]).startswith("https://"):
                st.link_button("Consulter la source originale", item["url"])
            if item.get("decision") == "ACTION" and not item.get("action_id"):
                st.info("Action retirée ; décision conservée dans l’historique de la veille.")
            elif item.get("decision") == "ACTION" and item.get("action_id"):
                st.success("Une action existe déjà pour cette information. La source originale est conservée.")
                # This is the same detail, with its usual server-side rights.
                detail_key = f"{key}_action"
                render_quality_detail(engine, actor, item["action_id"], key=detail_key)
                dialog = st.session_state.get(f"{detail_key}_dialog", {})
                if dialog and (_HAS_DISMISS_CALLBACK or dialog.pop("show", False)):
                    _action_dialog(engine, actor, detail_key)
            elif item.get("decision") == "NO_ACTION":
                st.info("Décision enregistrée : sans action nécessaire. Son motif est conservé dans le plan.")
                st.write(f"**Motif :** {item.get('decision_reason') or 'Motif conservé dans la décision'}")
            else:
                command_key = f"{key}_decision_command_{chosen}"
                if command_key not in st.session_state:
                    st.session_state[command_key] = uuid.uuid4().hex
                with st.form(f"{key}_decision_form_{chosen}", clear_on_submit=False):
                    choice = st.radio("Décision", ["ACTION", "NO_ACTION"], index=None,
                        format_func=lambda value: ("Suivre l’action existante dans le plan" if item.get("action_id") else "Créer une action dans le plan unique") if value == "ACTION" else "Sans action nécessaire", key=f"{key}_choice_{chosen}")
                    reason = st.text_area("Analyse / motif de la décision", key=f"{key}_reason_{chosen}")
                    with st.expander("Intitulé et contexte de l’action, si nécessaire"):
                        title = st.text_input("Action à réaliser", value=(item.get("title") or "")[:250], max_chars=250, key=f"{key}_title_{chosen}")
                        description = st.text_area("Contexte utile", value=(item.get("summary") or "")[:10000], max_chars=10000, key=f"{key}_description_{chosen}")
                        st.caption("Le texte original complet reste conservé dans la veille ; l’action peut en reprendre un résumé utile.")
                    submitted = st.form_submit_button("Enregistrer la décision", type="primary")
                if submitted:
                    if choice is None:
                        raise ValueError("Choisissez une décision. Rien n’est déclaré applicable ou réalisé automatiquement.")
                    watch.decide_item(engine, actor, chosen, decision=choice, reason=reason,
                        command_id=st.session_state[command_key], title=title, description=description)
                    st.success("Décision enregistrée ; la source originale est conservée.")
                    st.rerun()
        else:
            st.info("Aucune information pour ces filtres. Vérifiez le dernier contrôle réussi des sources.")
        with st.expander("Sources et contrôles", expanded=not sources):
            if sources:
                st.dataframe(pd.DataFrame([{"Source": row["name"], "Famille": row.get("category"),
                    "Active": bool(row.get("active")), "Configuration vérifiée": bool(row.get("configuration_validated")),
                    "Dernier succès": _timestamp(engine, actor, row.get("last_success_at")),
                    "Priorité": row.get("priority")} for row in sources]), hide_index=True, use_container_width=True)
                chosen_source = st.selectbox("Source à contrôler maintenant", list(by_id),
                    format_func=lambda value: by_id[value]["name"], key=f"{key}_collect_source")
                record = by_id[chosen_source]
                if st.button("Contrôler cette source maintenant", key=f"{key}_collect",
                    disabled=not (record.get("active") and record.get("configuration_validated"))):
                    with st.spinner("Contrôle de la source en cours…"):
                        result = watch.collect_source(engine, actor, chosen_source, trigger="MANUAL")
                    if result.get("status") in ("SUCCESS", "SUCCEEDED", "COMPLETED"):
                        st.success("Contrôle terminé. Le dernier succès de cette source est enregistré.")
                    else:
                        st.warning("Contrôle non abouti. Le dernier contrôle réussi est conservé ; consultez l’historique.")
                    st.caption(f"{result.get('new_items', 0)} nouvelle(s) information(s) · {result.get('new_versions', 0)} nouvelle(s) version(s).")
                    if result.get("error"):
                        st.write(result["error"])
            _watch_source_form(engine, actor, watch, sources, key)
        with st.expander("Historique des contrôles"):
            runs = watch.list_runs(engine, actor, source_id=source_id)
            if runs:
                st.dataframe(pd.DataFrame([{"Source": by_id.get(row.get("source_id"), {}).get("name") or "Source archivée", "Déclenchement": row.get("trigger") or row.get("trigger_kind"),
                    "Début": _timestamp(engine, actor, row.get("started_at")), "Fin": _timestamp(engine, actor, row.get("finished_at")),
                    "État": row.get("status"), "Nouvelles informations": row.get("new_items") or row.get("new_count") or 0,
                    "Versions modifiées": row.get("new_versions") or 0,
                    "Information de contrôle": row.get("error") or row.get("message") or ""} for row in runs]), hide_index=True, use_container_width=True)
            else:
                st.caption("Aucun contrôle enregistré. L’initialisation ne fabrique pas un historique passé.")
        with st.expander("Calendrier mensuel"):
            schedule_key = f"{key}_schedule_config"
            values = lambda row: {"enabled": bool(row.get("enabled")), "timezone": row.get("timezone") or "Europe/Paris",
                "hour": int(row.get("hour") or 0), "minute": int(row.get("minute") or 0),
                "validated": bool(row.get("configuration_validated"))}
            schedule = _configuration_snapshot(watch.get_schedule(engine, actor), schedule_key, values, "Le calendrier de veille")
            defaults = values(schedule)
            with st.form(f"{key}_schedule", clear_on_submit=False):
                enabled = st.checkbox("Activer le contrôle le premier jour du mois", value=defaults["enabled"], key=f"{schedule_key}_enabled")
                timezone = st.text_input("Fuseau de l’organisme", value=defaults["timezone"], key=f"{schedule_key}_timezone")
                hour = st.number_input("Heure", min_value=0, max_value=23, value=defaults["hour"], step=1, key=f"{schedule_key}_hour")
                minute = st.number_input("Minute", min_value=0, max_value=59, value=defaults["minute"], step=1, key=f"{schedule_key}_minute")
                validated = st.checkbox("Horaire et accès aux sources vérifiés", value=defaults["validated"], key=f"{schedule_key}_validated")
                st.caption("Une source en échec conserve sa date de dernier succès. Le lancement manuel actualise ce même point de reprise.")
                save = st.form_submit_button("Enregistrer le calendrier")
            if save:
                watch.save_schedule(engine, actor, enabled=enabled, configuration_validated=validated,
                    timezone=timezone, hour=int(hour), minute=int(minute), expected_version=schedule.get("row_version", schedule.get("version")))
                st.session_state.pop(f"{schedule_key}_snapshot", None)
                st.session_state[f"{key}_flash"] = "Calendrier enregistré."
                st.rerun()
        with st.expander("Parc technique et applications concernées"):
            _watch_technology_form(engine, actor, watch, key)
    except Exception as exc:
        _error(exc)


def _watch_source_form(engine, actor, watch, sources, key):
    import json
    mapping = {row["id"]: row for row in sources}
    pending = st.session_state.pop(f"{key}_next_source", None)
    if pending in mapping:
        st.session_state[f"{key}_edit_source"] = pending
    if st.session_state.get(f"{key}_edit_source") not in mapping:
        st.session_state[f"{key}_edit_source"] = None
    edit_id = st.selectbox("Ajouter ou modifier une source", [None] + list(mapping),
        format_func=lambda value: "Nouvelle source" if value is None else mapping[value]["name"], key=f"{key}_edit_source")
    technologies = {item["id"]: item for item in watch.list_technologies(engine, actor)}
    prefix = f"{key}_source_config_{edit_id}"

    def values(row):
        hosts = row.get("allowed_hosts") or []
        if isinstance(hosts, str):
            try:
                hosts = json.loads(hosts)
            except ValueError:
                hosts = [hosts]
        config = row.get("parser_config") or {}
        if isinstance(config, str):
            config = json.loads(config)
        return {"name": row.get("name") or "", "category": row.get("category") or "REGLEMENTAIRE",
                "url": row.get("url") or "", "scope": row.get("scope") or "", "priority": row.get("priority") or "NORMAL",
                "active": bool(row.get("active")), "format": row.get("format") or "RSS", "allowed": ", ".join(hosts),
                "parser": json.dumps(config, ensure_ascii=False), "overlap": int(row.get("overlap_days") or 14),
                "point_zero": _date(row.get("point_zero")), "technologies": [value for value in row.get("technology_ids", []) if value in technologies],
                "validated": bool(row.get("configuration_validated"))}

    row = _configuration_snapshot(mapping.get(edit_id, {}), prefix, values, "La source de veille")
    defaults = values(row)
    with st.form(f"{key}_source_form_{edit_id}", clear_on_submit=False):
        name = st.text_input("Nom de la source", value=defaults["name"], key=f"{prefix}_name")
        category = st.text_input("Famille", value=defaults["category"], key=f"{prefix}_category",
            help="Réglementation, métiers, pédagogie, handicap / accessibilité ou technologie.")
        url = st.text_input("Lien officiel HTTPS", value=defaults["url"], key=f"{prefix}_url")
        scope = st.text_area("Périmètre concerné", value=defaults["scope"], key=f"{prefix}_scope")
        priority_values = ["NORMAL", "LOW", "HIGH", "CRITICAL"]
        priority = st.selectbox("Priorité", priority_values, index=priority_values.index(defaults["priority"]),
            format_func=lambda value: {"NORMAL": "Normale", "LOW": "Faible", "HIGH": "Haute", "CRITICAL": "Critique"}[value], key=f"{prefix}_priority")
        active = st.checkbox("Source active", value=defaults["active"], key=f"{prefix}_active")
        with st.expander("Méthode de collecte et paramètres experts"):
            formats = ["RSS", "ATOM", "JSON", "HTML", "MANUAL"]
            format_value = st.selectbox("Format de la source", formats,
                index=formats.index(defaults["format"]), key=f"{prefix}_format",
                format_func=lambda value: "Contrôle manuel (PDF ou source non automatisable)" if value == "MANUAL" else value)
            allowed = st.text_input("Noms d’hôtes HTTPS autorisés (séparés par une virgule)", value=defaults["allowed"], key=f"{prefix}_allowed")
            parser = st.text_area("Règle d’extraction vérifiée (JSON)", value=defaults["parser"], key=f"{prefix}_parser",
                help="Paramètres d’extraction seulement. Aucun mot de passe ni jeton.")
            overlap = st.number_input("Recouvrement des contrôles (jours)", min_value=1, max_value=365, value=defaults["overlap"], step=1, key=f"{prefix}_overlap")
            point_zero = st.date_input("Point zéro de cette source (facultatif)", value=defaults["point_zero"], format=DATE_FORMAT, key=f"{prefix}_point_zero")
            technology_ids = st.multiselect("Technologies suivies par cette source", list(technologies),
                default=defaults["technologies"], key=f"{prefix}_technologies", format_func=lambda value: technologies[value]["name"])
            validated = st.checkbox("Configuration et règle d’extraction vérifiées pour cette source", value=defaults["validated"], key=f"{prefix}_validated")
        st.caption("Un lien seul ne promet pas une collecte universelle. L’activation exige une configuration vérifiée ; les accès privés ne sont pas contournés.")
        submitted = st.form_submit_button("Enregistrer la source")
    if submitted:
        try:
            config = json.loads(parser)
        except ValueError:
            raise ValueError("La règle d’extraction doit être un objet JSON valide.") from None
        # A date-only widget must not truncate a success cursor containing time.
        zero_value = row.get("point_zero") if point_zero == _date(row.get("point_zero")) else point_zero.isoformat() if point_zero else None
        saved_id = watch.save_source(engine, actor, source_id=edit_id, expected_version=row.get("row_version", row.get("version")),
            name=name, category=category, url=url, scope=scope, priority=priority, active=active,
            configuration_validated=validated, format=format_value,
            allowed_hosts=[host.strip() for host in allowed.split(",") if host.strip()], parser_config=config,
            overlap_days=int(overlap), technology_ids=technology_ids,
            point_zero=zero_value)
        st.session_state.pop(f"{prefix}_snapshot", None)
        st.session_state[f"{key}_next_source"] = saved_id
        st.session_state[f"{key}_flash"] = "Source enregistrée."
        st.rerun()
    if edit_id is not None:
        with st.expander("Retirer cette source du suivi"):
            st.caption("Une source déjà contrôlée est archivée avec son historique. Une source jamais contrôlée peut être retirée ; le motif est conservé.")
            with st.form(f"{prefix}_remove", clear_on_submit=False):
                reason = st.text_area("Motif du retrait de la source", key=f"{prefix}_remove_reason")
                remove = st.form_submit_button("Retirer cette source")
            if remove:
                result = watch.remove_source(engine, actor, edit_id, expected_version=row.get("row_version"), reason=reason)
                st.session_state.pop(f"{prefix}_snapshot", None)
                st.session_state[f"{key}_flash"] = "Source archivée ; son historique est conservé." if result.get("archived") else "Source retirée ; le motif est conservé."
                st.rerun()


def _watch_technology_form(engine, actor, watch, key):
    technologies = watch.list_technologies(engine, actor)
    if technologies:
        st.dataframe(pd.DataFrame([{"Technologie": row["name"], "Famille": row.get("family"),
            "Applications": row.get("applications"), "Version observée": row.get("observed_version") or "À confirmer",
            "Responsable technique": row.get("technical_owner") or "À confirmer"} for row in technologies]),
            use_container_width=True, hide_index=True)
    mapping = {row["id"]: row for row in technologies}
    pending = st.session_state.pop(f"{key}_next_technology", None)
    if pending in mapping:
        st.session_state[f"{key}_technology"] = pending
    edit_id = st.selectbox("Technologie", [None] + list(mapping),
        format_func=lambda value: "Nouvelle technologie" if value is None else mapping[value]["name"], key=f"{key}_technology")
    prefix = f"{key}_technology_config_{edit_id}"

    def values(row):
        applications_value = row.get("applications") or []
        if isinstance(applications_value, str):
            import json
            try:
                applications_value = json.loads(applications_value)
            except ValueError:
                applications_value = [applications_value]
        return {"name": row.get("name") or "", "family": row.get("family") or "", "url": row.get("official_url") or "",
                "applications": ", ".join(applications_value), "active": bool(row.get("active", True)), "publisher": row.get("publisher") or "",
                "environment": row.get("environment") or "", "observed_version": row.get("observed_version") or "", "model": row.get("model") or "",
                "owner": row.get("technical_owner") or "", "criticality": row.get("criticality") or "NORMAL"}

    row = _configuration_snapshot(mapping.get(edit_id, {}), prefix, values, "La fiche technique")
    defaults = values(row)
    with st.form(f"{key}_tech_form_{edit_id}", clear_on_submit=False):
        name = st.text_input("Nom", value=defaults["name"], key=f"{prefix}_name")
        family = st.text_input("Famille de technologie", value=defaults["family"], key=f"{prefix}_family")
        url = st.text_input("Référence officielle", value=defaults["url"], key=f"{prefix}_url")
        applications = st.text_input("Applications concernées (séparées par une virgule)", value=defaults["applications"], key=f"{prefix}_applications")
        active = st.checkbox("Technologie utilisée", value=defaults["active"], key=f"{prefix}_active")
        with st.expander("Versions et paramètres techniques"):
            publisher = st.text_input("Éditeur", value=defaults["publisher"], key=f"{prefix}_publisher")
            environment = st.text_input("Environnement observé", value=defaults["environment"], key=f"{prefix}_environment")
            observed_version = st.text_input("Version installée observée (vide = à confirmer)", value=defaults["observed_version"], key=f"{prefix}_observed_version")
            model = st.text_input("Modèle effectivement utilisé, si applicable", value=defaults["model"], key=f"{prefix}_model")
            owner = st.text_input("Responsable technique", value=defaults["owner"], key=f"{prefix}_owner")
            values = ["NORMAL", "LOW", "HIGH", "CRITICAL"]
            criticality = st.selectbox("Criticité", values, index=values.index(defaults["criticality"]), key=f"{prefix}_criticality",
                format_func=lambda value: {"NORMAL": "Normale", "LOW": "Faible", "HIGH": "Haute", "CRITICAL": "Critique"}[value])
        submitted = st.form_submit_button("Enregistrer la technologie")
    if submitted:
        saved_id = watch.save_technology(engine, actor, technology_id=edit_id, expected_version=row.get("row_version", row.get("version")),
            name=name, family=family, publisher=publisher, official_url=url,
            applications=[item.strip() for item in applications.split(",") if item.strip()], environment=environment,
            observed_version=observed_version, model=model, technical_owner=owner, criticality=criticality, active=active)
        st.session_state.pop(f"{prefix}_snapshot", None)
        st.session_state[f"{key}_next_technology"] = saved_id
        st.session_state[f"{key}_flash"] = "Technologie enregistrée sans modification des applications."
        st.rerun()
