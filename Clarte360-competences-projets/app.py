from __future__ import annotations

import streamlit as st

from clarte360_cp.application import bootstrap_case
from clarte360_cp.connectors import LaunchTokenError
from clarte360_cp.framework.app_identity import load_app_identity
from clarte360_cp.framework.branding import apply_framework_css
from clarte360_cp.framework.config import LOGO_PATH, APP_SHORT_NAME, session_limit_minutes
from clarte360_cp.framework.session import SessionExpiredError, initialize_session, touch_activity
from clarte360_cp.ui.entry import render_access_recovery_help, render_admin_upload, resolve_launch_context
from clarte360_cp.ui.pages import render_home

identity = load_app_identity()
st.set_page_config(page_title=APP_SHORT_NAME, page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "C360", layout="wide")
apply_framework_css()

if str(st.query_params.get("mode", "")).lower() == "upload_only":
    render_admin_upload()
    st.stop()

try:
    launch = resolve_launch_context()
    boot = bootstrap_case(launch)
except SessionExpiredError:
    st.warning(
        f"Votre session a expiré après {session_limit_minutes(st.secrets)} minutes sans interaction."
    )
    render_access_recovery_help()
    st.stop()
except LaunchTokenError as exc:
    st.error(str(exc))
    render_access_recovery_help()
    st.stop()
except Exception:
    st.error("Le dossier ne peut pas être ouvert pour le moment. Aucune donnée n'a été modifiée de façon silencieuse."); st.stop()

initialize_session(launch, boot.case_id, boot.row_version)
# Les fragments automatiques contrôlent l'accès mais n'appellent jamais ceci.
touch_activity()
render_home(launch, boot)
