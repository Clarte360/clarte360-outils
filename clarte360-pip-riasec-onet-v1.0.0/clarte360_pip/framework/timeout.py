from __future__ import annotations

from datetime import datetime

from .config import DEFAULT_SESSION_LIMIT_MINUTES


def session_limit_minutes(secrets=None) -> int:
    try:
        section = secrets.get("security", {}) if secrets else {}
        return int(section.get("session_timeout_minutes", DEFAULT_SESSION_LIMIT_MINUTES))
    except Exception:
        return DEFAULT_SESSION_LIMIT_MINUTES


def is_timed_out(last_activity_at: str | None, now: datetime | None = None, limit_minutes: int = DEFAULT_SESSION_LIMIT_MINUTES) -> bool:
    if not last_activity_at:
        return False
    try:
        last = datetime.fromisoformat(last_activity_at)
    except ValueError:
        return False
    current = now or datetime.now()
    return (current - last).total_seconds() > limit_minutes * 60


def enforce_timeout() -> None:
    import streamlit as st

    limit = session_limit_minutes(st.secrets)
    if is_timed_out(st.session_state.get("last_activity_at"), limit_minutes=limit):
        st.session_state.navigation_page = "timeout"
