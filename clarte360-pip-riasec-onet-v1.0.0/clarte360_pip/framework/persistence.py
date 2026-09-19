from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from clarte360_pip.version import APP_VERSION, FRAMEWORK_VERSION
from clarte360_pip.framework.validation import MAX_JSON_UPLOAD_BYTES, ValidationError, validate_safe_id, validate_score

# Pages that represent an actual point in the beneficiary journey. Utility pages
# (RGPD consultation, contact and timeout) must never become a timeout-resume target.
RESUMABLE_PAGES = {
    "accueil",
    "pip_intro",
    "pip_questionnaire",
    "pip_complete",
    "pip_results_gate",
    "onet_pending",
    "onet_intro",
    "onet_questionnaire",
    "combined_results",
    "feeling",
    "finished",
}
TRANSIENT_PAGES = {"timeout", "rgpd", "contact"}


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def infer_resume_page(state: dict[str, Any]) -> str:
    """Infer the most useful page without destroying an existing passation."""
    onet = state.get("onet_state") or {}
    pip = state.get("pip_state") or {}
    journey = state.get("journey", "PIP_SEUL")

    if isinstance(onet, dict) and onet.get("completed"):
        return "combined_results"
    if isinstance(onet, dict) and onet.get("questions") and not onet.get("completed"):
        return "onet_questionnaire"
    if isinstance(pip, dict) and pip.get("completed"):
        if journey == "PIP_PUIS_ONET60":
            return "onet_intro"
        return "pip_results_gate"
    if isinstance(pip, dict) and (pip.get("order") or pip.get("answers")):
        return "pip_questionnaire"
    return "pip_intro"


def resolve_resume_page(state: dict[str, Any]) -> str:
    current = str(state.get("navigation_page") or "")
    last_useful = str(state.get("last_useful_page") or "")
    if current in RESUMABLE_PAGES:
        return current
    if last_useful in RESUMABLE_PAGES:
        return last_useful
    return infer_resume_page(state)


def build_snapshot(session_state: dict[str, Any]) -> dict[str, Any]:
    launch = session_state.get("launch_context")
    resume_page = resolve_resume_page(session_state)
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
        "public_email_verified_at": session_state.get("public_email_verified_at"),
        "public_callback_requested": bool(session_state.get("public_callback_requested")),
        "public_callback_requested_at": session_state.get("public_callback_requested_at"),
        "study_consent": bool(session_state.get("study_consent")),
        "onet_selected_timing": session_state.get("onet_selected_timing"),
        # navigation_page is deliberately a resume destination, never "timeout".
        "navigation_page": resume_page,
        "last_useful_page": resume_page,
        "journey": session_state.get("journey", "PIP_SEUL"),
        "pip_state": _jsonable(session_state.get("pip_state", {})),
        "pip_scoring": _jsonable(session_state.get("pip_scoring", {})) if bool(session_state.get("pip_state", {}).get("completed")) else {},
        "onet_state": _jsonable(session_state.get("onet_state", {})),
        "feeling": _jsonable(session_state.get("feeling", {})),
        "session_history": _jsonable(session_state.get("session_history", [])),
        "report_documents": _jsonable(session_state.get("report_documents", [])),
        "final_event_published": bool(session_state.get("final_event_published")),
        "completed_at": session_state.get("completed_at"),
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
    if len(payload) > 45:
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

    nav = payload.get("navigation_page")
    if nav == "timeout":
        # Legacy timeout JSONs are accepted and repaired on restore.
        pass
    elif nav is not None and nav not in RESUMABLE_PAGES and nav not in {"rgpd", "contact"}:
        errors.append("Page de reprise invalide.")

    pip_state = payload.get("pip_state", {})
    if not isinstance(pip_state, dict):
        errors.append("État PIP invalide.")
    else:
        answers = pip_state.get("answers", {})
        # Compatibility: old 120-item snapshots remain structurally acceptable.
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

    for key in (
        "passation_id", "session_id", "pip_state", "pip_scoring", "onet_state",
        "feeling", "session_history", "public_participant_id", "public_identity",
        "public_access_verified", "public_marketing_opt_in", "public_interests",
        "public_other_interest", "public_email_verified_at", "public_callback_requested",
        "public_callback_requested_at", "study_consent", "onet_selected_timing",
        "rgpd_acceptance", "report_documents", "final_event_published", "completed_at",
    ):
        if key in payload:
            session_state[key] = payload[key]
    session_state["journey"] = payload.get("journey", "PIP_SEUL")

    # Repair legacy timeout snapshots and utility-page snapshots.
    candidate = payload.get("navigation_page")
    last_useful = payload.get("last_useful_page")
    if candidate in RESUMABLE_PAGES:
        resume_page = candidate
    elif last_useful in RESUMABLE_PAGES:
        resume_page = last_useful
    else:
        resume_page = infer_resume_page(payload)
    session_state["navigation_page"] = resume_page
    session_state["last_useful_page"] = resume_page

    # A restored session starts with a fresh inactivity clock.
    session_state["last_activity_at"] = datetime.now().isoformat(timespec="seconds")
    session_state.pop("timeout_at", None)
    session_state["resume_restored"] = True
