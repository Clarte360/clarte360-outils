from __future__ import annotations

import streamlit as st

from clarte360_pip.connectors.gestion_actions import GestionActionsPort
from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.framework.config import load_gestion_actions_settings


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
        # Public mode must not accept Clarté360 dossier identifiers even if a user adds them to the URL.
        forbidden = ("beneficiary_id", "action_id", "participant_id", "prescription_id", "launch")
        if any(_query_value(name) for name in forbidden):
            raise ValueError("Le point d'entrée PUBLIC ne peut contenir aucun identifiant Clarté360.")
        ctx = LaunchContext(mode=RunMode.PUBLIC)
        ctx.validate()
        return ctx

    if mode_raw == "accompagnement":
        token = _query_value("launch")
        if not token:
            raise ValueError("Lien d'accompagnement incomplet : jeton de lancement absent.")
        settings = load_gestion_actions_settings(st.secrets)
        port = GestionActionsPort(settings.launch_signing_key)
        return port.resolve_launch(token)

    raise ValueError("Point d'entrée invalide.")
