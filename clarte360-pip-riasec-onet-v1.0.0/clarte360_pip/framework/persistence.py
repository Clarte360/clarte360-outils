from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from clarte360_pip.version import APP_VERSION, FRAMEWORK_VERSION
from clarte360_pip.framework.validation import MAX_JSON_UPLOAD_BYTES, ValidationError, validate_safe_id, validate_score


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
        "public_participant_id": session_state.get("public_participant_id"),
        "public_identity": _jsonable(session_state.get("public_identity", {})),
        "public_access_verified": bool(session_state.get("public_access_verified")),
        "public_marketing_opt_in": bool(session_state.get("public_marketing_opt_in")),
        "public_interests": _jsonable(session_state.get("public_interests", [])),
        "public_other_interest": session_state.get("public_other_interest", ""),
        "study_consent": bool(session_state.get("study_consent")),
        "onet_selected_timing": session_state.get("onet_selected_timing"),
        "navigation_page": session_state.get("navigation_page"),
        "journey": session_state.get("journey", "PIP_SEUL"),
        "pip_state": _jsonable(session_state.get("pip_state", {})),
        "pip_scoring": _jsonable(session_state.get("pip_scoring", {})) if bool(session_state.get("pip_state", {}).get("completed")) else {},
        "onet_state": _jsonable(session_state.get("onet_state", {})),
        "feeling": _jsonable(session_state.get("feeling", {})),
        "session_history": _jsonable(session_state.get("session_history", [])),
    }


def snapshot_bytes(session_state: dict[str, Any]) -> bytes:
    return json.dumps(build_snapshot(session_state), ensure_ascii=False, indent=2).encode("utf-8")


def decode_snapshot_bytes(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, (bytes, bytearray)):
        raise ValidationError("Fichier de sauvegarde invalide.")
    if not raw:
        raise ValidationError("Le fichier de sauvegarde est vide.")
    if len(raw) > MAX_JSON_UPLOAD_BYTES:
        raise ValidationError("Le fichier de sauvegarde est trop volumineux (2 Mo maximum).")
    try:
        payload = json.loads(bytes(raw).decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ValidationError("Le fichier de sauvegarde doit être encodé en UTF-8.") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError("Le fichier de sauvegarde ne contient pas un JSON valide.") from exc
    if not isinstance(payload, dict):
        raise ValidationError("La sauvegarde doit contenir un objet JSON.")
    return payload


def validate_snapshot(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["Sauvegarde JSON invalide."]
    if len(payload) > 40:
        errors.append("Sauvegarde anormalement volumineuse ou incompatible.")
    if payload.get("schema") != "clarte360.pip.run.v1":
        errors.append("Schéma de sauvegarde incompatible.")
    try:
        validate_safe_id(payload.get("passation_id"), "passation_id")
    except ValidationError as exc:
        errors.append(str(exc))

    journey = payload.get("journey", "PIP_SEUL")
    if journey not in {"PIP_SEUL", "PIP_PUIS_ONET60"}:
        errors.append("Parcours de sauvegarde invalide.")

    pip_state = payload.get("pip_state", {})
    if not isinstance(pip_state, dict):
        errors.append("État PIP invalide.")
    else:
        answers = pip_state.get("answers", {})
        if not isinstance(answers, dict) or len(answers) > 120:
            errors.append("Réponses PIP invalides.")
        else:
            for key, value in answers.items():
                try:
                    validate_safe_id(key, "identifiant de question PIP")
                    validate_score(value, "Réponse PIP")
                except ValidationError as exc:
                    errors.append(str(exc)); break
        try:
            index = int(pip_state.get("index", 0))
            if not 0 <= index <= 119:
                errors.append("Position PIP invalide.")
        except (TypeError, ValueError):
            errors.append("Position PIP invalide.")

    onet_state = payload.get("onet_state", {})
    if onet_state not in ({}, None) and not isinstance(onet_state, dict):
        errors.append("État O*NET invalide.")
    elif isinstance(onet_state, dict):
        answers = onet_state.get("answers", {})
        if not isinstance(answers, dict) or len(answers) > 60:
            errors.append("Réponses O*NET invalides.")
        else:
            for key, value in answers.items():
                try:
                    q = int(key)
                    if not 1 <= q <= 60:
                        raise ValidationError("Identifiant de question O*NET invalide.")
                    validate_score(value, "Réponse O*NET")
                except (TypeError, ValueError, ValidationError) as exc:
                    errors.append(str(exc)); break

    if not isinstance(payload.get("public_identity", {}), dict):
        errors.append("Identité publique invalide.")
    if not isinstance(payload.get("session_history", []), list):
        errors.append("Historique de session invalide.")
    return errors


def restore_snapshot(payload: dict[str, Any], session_state: Any) -> None:
    errors = validate_snapshot(payload)
    if errors:
        raise ValidationError(" ".join(errors))
    for key in ("passation_id","session_id","navigation_page","pip_state","pip_scoring","onet_state","feeling","session_history","public_participant_id","public_identity","public_access_verified","public_marketing_opt_in","public_interests","public_other_interest","study_consent","onet_selected_timing"):
        if key in payload:
            session_state[key] = payload[key]
    session_state["journey"] = payload.get("journey", "PIP_SEUL")
