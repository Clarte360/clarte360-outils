from __future__ import annotations
import json
from datetime import datetime
from typing import Any
from clarte360_ipip.version import APP_VERSION, FRAMEWORK_VERSION
from .validation import ValidationError, validate_safe_id, validate_score

SCHEMA = "clarte360.ipipneo.run.v1"


def build_snapshot(session_state: dict[str, Any]) -> dict[str, Any]:
    answers = {str(k): validate_score(v, f"Réponse {k}") for k, v in dict(session_state.get("answers", {})).items()}
    run_id = validate_safe_id(session_state.get("run_id"), "run_id")
    return {
        "schema": SCHEMA,
        "app_version": APP_VERSION,
        "framework_version": FRAMEWORK_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": run_id,
        "answers": answers,
        "block": int(session_state.get("block", 0)),
        "stage": str(session_state.get("stage", "questionnaire")),
        "rgpd_acceptance": session_state.get("rgpd_acceptance"),
    }


def snapshot_bytes(session_state: dict[str, Any]) -> bytes:
    return json.dumps(build_snapshot(session_state), ensure_ascii=False, indent=2).encode("utf-8")


def decode_snapshot_bytes(raw: bytes) -> dict[str, Any]:
    if len(raw) > 2 * 1024 * 1024:
        raise ValidationError("Sauvegarde trop volumineuse.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Sauvegarde JSON invalide.") from exc
    if payload.get("schema") != SCHEMA:
        raise ValidationError("Format de sauvegarde incompatible.")
    return payload
