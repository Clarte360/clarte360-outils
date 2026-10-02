from __future__ import annotations
from datetime import datetime
import streamlit as st


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def initialize_session() -> None:
    defaults = {
        "navigation_page": "accueil",
        "last_activity_at": now_iso(),
        "access_history": [],
        "rgpd_acceptance": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def touch_activity(event: str = "ui") -> None:
    st.session_state.last_activity_at = now_iso()
    history = st.session_state.setdefault("access_history", [])
    history.append({"at": st.session_state.last_activity_at, "event": event})
    if len(history) > 100:
        del history[:-100]
