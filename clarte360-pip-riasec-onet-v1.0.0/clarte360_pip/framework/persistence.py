from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from clarte360_pip.version import APP_VERSION, FRAMEWORK_VERSION


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def build_snapshot(session_state: dict[str, Any]) -> dict[str, Any]:
    launch = session_state.get("launch_context")
    return {
        "schema": "clarte360.pip.run.v1",
        "app_version": APP_VERSION,
        "framework_version": FRAMEWORK_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "passation_id": session_state.get("passation_id"),
        "session_id": session_state.get("session_id"),
        "launch_context": _jsonable(launch),
        "rgpd_acceptance": _jsonable(session_state.get("rgpd_acceptance")),
        "navigation_page": session_state.get("navigation_page"),
        "journey": session_state.get("journey", "PIP_SEUL"),
        "pip_state": _jsonable(session_state.get("pip_state", {})),
        "pip_scoring": _jsonable(session_state.get("pip_scoring", {})),
        "onet_state": _jsonable(session_state.get("onet_state", {})),
        "feeling": _jsonable(session_state.get("feeling", {})),
        "session_history": _jsonable(session_state.get("session_history", [])),
    }


def snapshot_bytes(session_state: dict[str, Any]) -> bytes:
    return json.dumps(build_snapshot(session_state), ensure_ascii=False, indent=2).encode("utf-8")


def validate_snapshot(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != "clarte360.pip.run.v1":
        errors.append("Schema de sauvegarde incompatible.")
    if not payload.get("passation_id"):
        errors.append("passation_id manquant.")
    if not isinstance(payload.get("pip_state", {}), dict):
        errors.append("pip_state invalide.")
    return errors

def restore_snapshot(payload: dict[str, Any], session_state: Any) -> None:
    errors=validate_snapshot(payload)
    if errors: raise ValueError(" ".join(errors))
    for key in ("passation_id","session_id","navigation_page","pip_state","pip_scoring","onet_state","feeling","session_history"):
        if key in payload: session_state[key]=payload[key]
    session_state["journey"]=payload.get("journey","PIP_SEUL")
