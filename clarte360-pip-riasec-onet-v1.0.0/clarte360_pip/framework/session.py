from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import streamlit as st

from clarte360_pip.domain import LaunchContext
from clarte360_pip.framework.persistence import RESUMABLE_PAGES


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def initialize_session(launch: LaunchContext) -> None:
    defaults = {
        "passation_id": str(uuid4()),
        "session_id": str(uuid4()),
        "created_at": now_iso(),
        "started_at": None,
        "completed_at": None,
        "session_history": [],
        "access_history": [],
        "rgpd_acceptance": None,
        "navigation_page": "accueil",
        "last_useful_page": "accueil",
        "rgpd_return_page": "accueil",
        "launch_context": launch,
        "pip_state": {},
        "technical_state": {},
        "public_access_verified": False,
        "public_identity": {},
        "public_marketing_opt_in": False,
        "public_interests": [],
        "public_other_interest": "",
        "public_email_verified_at": None,
        "public_callback_requested": False,
        "public_callback_requested_at": None,
        "study_consent": False,
        "onet_selected_timing": None,
        "last_activity_at": now_iso(),
        "report_documents": [],
        "final_event_published": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def remember_current_page() -> None:
    page = st.session_state.get("navigation_page")
    if page in RESUMABLE_PAGES:
        st.session_state.last_useful_page = page


def touch_activity(event: str = "ui") -> None:
    st.session_state.last_activity_at = now_iso()
    st.session_state.access_history.append({"at": st.session_state.last_activity_at, "event": event})
