from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import streamlit as st

from clarte360_pip.domain import LaunchContext


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
        "launch_context": launch,
        "pip_state": {},
        "technical_state": {},
        "last_activity_at": now_iso(),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def touch_activity(event: str = "ui") -> None:
    st.session_state.last_activity_at = now_iso()
    st.session_state.access_history.append({"at": st.session_state.last_activity_at, "event": event})
