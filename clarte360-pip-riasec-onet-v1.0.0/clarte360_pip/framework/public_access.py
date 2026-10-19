from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import PERSISTENT_DATA_DIR, SmtpSettings
from .smtp import send_email
from .storage_io import atomic_json
from .validation import (
    ValidationError, validate_access_code, validate_email, validate_free_text,
    validate_optional_short_text, validate_person_name, validate_phone, validate_safe_id,
    validate_string_list,
)

PUBLIC_DIR = PERSISTENT_DATA_DIR / "public"
LEADS_DIR = PUBLIC_DIR / "leads"
STUDY_DIR = PUBLIC_DIR / "study"
def normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def validated_public_identity(data: dict[str, Any]) -> dict[str, str]:
    return {
        "first_name": validate_person_name(data.get("first_name"), "Prénom"),
        "last_name": validate_person_name(data.get("last_name"), "Nom"),
        "job_title": validate_optional_short_text(data.get("job_title"), "Fonction / titre"),
        "company": validate_optional_short_text(data.get("company"), "Entreprise / organisation"),
        "phone": validate_phone(data.get("phone")),
        "email": validate_email(data.get("email")),
    }


def validate_public_identity(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    checks = (
        lambda: validate_person_name(data.get("first_name"), "Prénom"),
        lambda: validate_person_name(data.get("last_name"), "Nom"),
        lambda: validate_phone(data.get("phone")),
        lambda: validate_email(data.get("email")),
        lambda: validate_optional_short_text(data.get("job_title"), "Fonction / titre"),
        lambda: validate_optional_short_text(data.get("company"), "Entreprise / organisation"),
    )
    for check in checks:
        try:
            check()
        except ValidationError as exc:
            errors.append(str(exc))
    return errors


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_json(path, payload)


def save_public_lead(participant_id: str, identity: dict[str, Any], marketing_opt_in: bool, verified: bool, interests: list[str] | None = None, other_interest: str = "") -> Path:
    participant_id = validate_safe_id(participant_id, "participant_id") or ""
    identity = validated_public_identity(identity)
    interests = list(validate_string_list(interests or [], "Centres d’intérêt", max_items=10))
    other_interest = validate_free_text(other_interest, "Autre intérêt", max_len=500)
    payload = {
        "participant_id": participant_id,
        "identity": identity,
        "marketing_opt_in": bool(marketing_opt_in),
        "interests": interests,
        "other_interest": other_interest,
        "email_verified": bool(verified),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    path = LEADS_DIR / f"{participant_id}.json"
    _atomic_json(path, payload)
    return path


def generate_access_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def code_digest(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def issue_public_code(identity: dict[str, Any], smtp: SmtpSettings, ttl_minutes: int = 15) -> tuple[bool, str, dict[str, Any]]:
    identity = validated_public_identity(identity)
    if not 5 <= int(ttl_minutes) <= 60:
        raise ValidationError("Durée de validité du code incohérente.")
    code = generate_access_code()
    expires = datetime.now() + timedelta(minutes=ttl_minutes)
    state = {"digest": code_digest(code), "expires_at": expires.isoformat(timespec="seconds"), "attempts": 0, "email": normalize_email(identity["email"])}
    body = (
        f"Bonjour {str(identity.get('first_name','')).strip()},\n\n"
        f"Votre code d'accès au PIP RIASEC Clarté360 est : {code}\n\n"
        f"Ce code est valable {ttl_minutes} minutes.\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\nClarté360"
    )
    ok, message = send_email(smtp, "Votre code d'accès PIP RIASEC Clarté360", body, normalize_email(str(identity["email"])))
    return ok, message, state


def verify_public_code(code: str, state: dict[str, Any], expected_email: str | None = None) -> bool:
    if expected_email is not None and normalize_email(state.get("email")) != normalize_email(expected_email):
        return False
    if not state or int(state.get("attempts", 0)) >= 6: return False
    try:
        code = validate_access_code(code)
    except ValidationError:
        return False
    try:
        if datetime.now() > datetime.fromisoformat(str(state["expires_at"])): return False
    except Exception:
        return False
    state["attempts"] = int(state.get("attempts", 0)) + 1
    return secrets.compare_digest(code_digest(code.strip()), str(state.get("digest", "")))


def new_study_id() -> str:
    """Independent pseudonym: never derived from CRM/contact/session identifiers."""
    return secrets.token_hex(16)


def pseudonym_for(participant_id: str) -> str:
    """Legacy helper retained only for old snapshot compatibility; do not use for new study records."""
    return hashlib.sha256(("clarte360-pip-study:" + participant_id).encode("utf-8")).hexdigest()[:24]


STUDY_SCHEMA = "clarte360.pip.public-study.v1"
STUDY_FORBIDDEN_KEYS = {
    "first_name", "last_name", "email", "phone", "identity", "public_identity",
    "crm_id", "contact_id", "beneficiary_id", "action_id", "participant_id",
    "public_participant_id", "prescription_id", "passation_id", "source_ref",
}


def _assert_study_payload_separation(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in STUDY_FORBIDDEN_KEYS:
                raise ValueError(f"Clé interdite dans le dataset étude: {path}.{key}")
            _assert_study_payload_separation(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_study_payload_separation(nested, f"{path}[{index}]")


def save_public_study_record(session_state: dict[str, Any]) -> Path | None:
    if not bool(session_state.get("study_consent")):
        return None
    pip_state = session_state.get("pip_state", {}) or {}
    study_id = str(session_state.get("public_study_id") or "").strip() or new_study_id()
    study_id = validate_safe_id(study_id, "study_id") or ""
    if study_id in {".", ".."}:
        raise ValidationError("Identifiant etude invalide.")
    session_state["public_study_id"] = study_id
    pip_scoring = dict(session_state.get("pip_scoring", {}) or {})
    onet_state = dict(session_state.get("onet_state", {}) or {})
    payload = {
        "schema": STUDY_SCHEMA,
        "study_id": study_id,
        "journey": session_state.get("journey", "PIP_SEUL"),
        "onet_selected_timing": session_state.get("onet_selected_timing"),
        "pip_bank_version": pip_state.get("bank_version"),
        "pip_scoring_version": pip_scoring.get("algorithm_version"),
        "pip_answers": pip_state.get("answers", {}),
        "pip_scoring": pip_scoring,
        "onet_state": onet_state,
        "feeling": session_state.get("feeling", {}),
        "study_consent": True,
        # A study record may legitimately exist before feeling. Existence never means TERMINE.
        "status": "TERMINE" if bool(session_state.get("completed_at") and session_state.get("feeling") and session_state.get("restitution_presented")) else "EN_COURS",
        "completed_at": session_state.get("completed_at") if bool(session_state.get("feeling") and session_state.get("restitution_presented")) else None,
    }
    _assert_study_payload_separation(payload)
    path = STUDY_DIR / f"{payload['study_id']}.json"
    _atomic_json(path, payload)
    return path


def verified_public_email(state) -> str | None:
    """A client-imported Boolean is not an e-mail verification proof."""
    if not state.get('public_access_verified'):
        return None
    try:
        participant = validate_safe_id(state.get('public_participant_id'), 'participant_id')
        if participant in {'.', '..'}:
            return None
        address = validate_email((state.get('public_identity') or {}).get('email'))
        path = LEADS_DIR / f'{participant}.json'
        record = json.loads(path.read_text(encoding='utf-8'))
        if (record.get('participant_id') == participant and record.get('email_verified') is True
                and normalize_email((record.get('identity') or {}).get('email')) == address):
            return address
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return None


def enforce_public_verification(state) -> None:
    """Preserve progress but require a new code when a restored recipient is untrusted."""
    if verified_public_email(state):
        return
    from .persistence import infer_resume_page
    progress = bool((state.get('pip_state') or {}).get('order') or (state.get('onet_state') or {}).get('questions'))
    state['public_access_verified'] = False
    state['public_email_verified_at'] = None
    if progress:
        target = state.get('navigation_page')
        if target not in {'accueil', 'rgpd', 'contact', 'timeout'}:
            state['public_verification_return_page'] = target or infer_resume_page(dict(state))
            state['navigation_page'] = 'accueil'
        state['public_home_choice'] = 'resume'


def restore_public_upload(payload, state) -> str:
    from .persistence import restore_snapshot, infer_resume_page
    context = payload.get('launch_context') or {}
    if context.get('mode', 'PUBLIC') != 'PUBLIC':
        raise ValidationError("Une sauvegarde accompagnee ne peut pas etre importee en mode public.")
    # Clear prior e-mail challenges so they cannot authorize a changed import.
    restored = {}
    restore_snapshot(payload, restored)
    for key in ('public_code_state', 'public_verification_return_page', '_final_pdf_cache'):
        state.pop(key, None)
    state.update(restored)
    state['navigation_page'] = infer_resume_page(dict(state))
    state['public_home_choice'] = 'resume'
    enforce_public_verification(state)
    return state['navigation_page']
