from __future__ import annotations

import streamlit as st

from clarte360_pip.domain import LaunchContext, RunMode


def _query_value(name: str) -> str | None:
    try:
        value = st.query_params.get(name)
    except Exception:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return str(value) if value is not None else None


def resolve_launch_context() -> LaunchContext:
    mode_raw = (_query_value("mode") or "public").strip().lower()
    if mode_raw == "public":
        ctx = LaunchContext(mode=RunMode.PUBLIC)
        ctx.validate()
        return ctx
    if mode_raw == "accompagnement":
        # L1-A accepts explicit dev identifiers only to prove the domain boundary.
        # Signed token verification belongs to the future Gestion des actions connector increment.
        ctx = LaunchContext(
            mode=RunMode.ACCOMPANIMENT,
            beneficiary_id=_query_value("beneficiary_id"),
            action_id=_query_value("action_id"),
            participant_id=_query_value("participant_id"),
            prescription_id=_query_value("prescription_id"),
            raw={"entry": "dev-scaffold-l1a"},
        )
        ctx.validate()
        return ctx
    raise ValueError("Point d'entree invalide.")
