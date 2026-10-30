from __future__ import annotations

import os

from clarte360_cp.connectors.gestion_actions import LaunchTokenError
from clarte360_cp.connectors.gestion_actions import verify_admin_upload_token
from clarte360_cp.connectors.gda_documents import GDAError, GDADocumentClient, load_gda_settings, renew_session_launch_token
from clarte360_cp.framework.config import load_connector_settings, session_limit_minutes
from clarte360_cp.framework.session import invalidate_session, resolve_session_launch


def resolve_launch_context():
    import streamlit as st
    params = st.query_params
    if str(params.get("mode", "")).lower() != "accompagnement":
        invalidate_session(st.session_state)
        raise LaunchTokenError("Accès C&P réservé au mode accompagnement sécurisé.")
    token = str(params.get("launch", "")).strip()
    settings = load_connector_settings(st.secrets)
    if not settings.configured:
        invalidate_session(st.session_state)
        raise LaunchTokenError("Connecteur de lancement sécurisé non configuré.")
    launch = resolve_session_launch(
        st.session_state, token, settings.launch_signing_key or "",
        limit_minutes=session_limit_minutes(st.secrets),
    )
    # When the live GDA bridge is configured, re-sign only this authenticated
    # server session, then make GDA recheck current rights on every app rerun.
    gda_settings = load_gda_settings(st.secrets)
    if gda_settings.configured:
        live_token = renew_session_launch_token(launch, settings.launch_signing_key or "")
        try:
            authorized = GDADocumentClient(gda_settings, live_token).check_session()
        except GDAError as exc:
            if str(exc).startswith("Accès refusé"):
                invalidate_session(st.session_state)
                raise LaunchTokenError("L’affectation au dossier a changé. Revenez dans Gestion des Actions pour rouvrir le bilan.") from exc
            raise
        if not authorized:
            invalidate_session(st.session_state)
            raise LaunchTokenError("L’affectation au dossier a changé. Revenez dans Gestion des Actions pour rouvrir le bilan.")
        token = live_token
    # Kept in Streamlit's server-side session only. It is never rendered or logged.
    st.session_state["gda_launch_token"] = token
    return launch


def render_access_recovery_help() -> None:
    import streamlit as st

    if os.getenv("CLARTE360_GO21_SYNC_PROBE", "").strip() == "1":
        st.info(
            "Pour reprendre cette recette, utilisez le raccourci de votre rôle : "
            "`1_OUVRIR_ACCOMPAGNATEUR.cmd` ou `2_OUVRIR_BENEFICIAIRE.cmd`. "
            "Gardez le serveur ouvert et ne relancez pas le fichier `0_DEMARRER`. "
            "Les réponses déjà enregistrées sont conservées."
        )
    else:
        st.info(
            "Revenez depuis Gestion des Actions avec un nouveau lien pour reprendre votre dossier. "
            "Les réponses déjà enregistrées sont conservées."
        )


def render_admin_upload() -> None:
    """Upload-only page for an authenticated GDA admin; no case or document listing."""
    import streamlit as st
    settings = load_connector_settings(st.secrets)
    token = str(st.query_params.get("launch", "")).strip()
    try:
        context = verify_admin_upload_token(token, settings.launch_signing_key or "")
    except LaunchTokenError as exc:
        st.error(str(exc)); return
    gda_settings = load_gda_settings(st.secrets)
    st.title("Déposer un document dans l’espace partagé")
    st.caption("Accès administrateur limité au dépôt pour le dossier prescrit. Cette page ne permet pas de consulter la liste ni le contenu des documents ou du bilan.")
    if not gda_settings.configured:
        st.error("Le connecteur documentaire Gestion des Actions n’est pas configuré."); return
    upload = st.file_uploader("Choisir un document", key="cp_admin_upload_file")
    if st.button("Déposer dans Gestion des Actions", type="primary", disabled=upload is None):
        try:
            document = GDADocumentClient(gda_settings, token).put_unlinked(
                upload.name, upload.getvalue(), mime_type=upload.type,
            )
            st.success("Document déposé dans l’espace partagé. L’accompagnateur le reliera manuellement au besoin du bilan.")
            st.caption(f"Référence de dépôt …{document['source_ref'][-8:]}")
        except GDAError as exc:
            st.error(str(exc))
