from __future__ import annotations
import streamlit as st


def query_value(name: str) -> str | None:
    try:
        value = st.query_params.get(name)
    except Exception:
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value is not None else None


def accompanied_launch_token() -> str:
    mode = (query_value("mode") or "accompagnement").strip().lower()
    if mode != "accompagnement":
        raise ValueError("Cette version est réservée au mode ACCOMPAGNEMENT.")
    token = (query_value("launch") or "").strip()
    if not token:
        raise ValueError("Lien d'accompagnement incomplet : jeton de lancement absent.")
    return token
