from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import PERSISTENT_DATA_DIR, SmtpSettings
from .smtp import send_email

PUBLIC_DIR = PERSISTENT_DATA_DIR / "public"
LEADS_DIR = PUBLIC_DIR / "leads"
STUDY_DIR = PUBLIC_DIR / "study"
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def validate_public_identity(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "first_name": "Prénom", "last_name": "Nom", "job_title": "Fonction / titre",
        "company": "Entreprise / organisation", "phone": "Téléphone", "email": "E-mail",
    }
    for key, label in required.items():
        if not str(data.get(key, "")).strip(): errors.append(f"{label} est obligatoire.")
    if data.get("email") and not _EMAIL_RE.match(normalize_email(str(data["email"]))):
        errors.append("Adresse e-mail invalide.")
    return errors


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def save_public_lead(participant_id: str, identity: dict[str, Any], marketing_opt_in: bool, verified: bool) -> Path:
    payload = {
        "participant_id": participant_id,
        "identity": {**identity, "email": normalize_email(str(identity.get("email", "")))},
        "marketing_opt_in": bool(marketing_opt_in),
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
    code = generate_access_code()
    expires = datetime.now() + timedelta(minutes=ttl_minutes)
    state = {"digest": code_digest(code), "expires_at": expires.isoformat(timespec="seconds"), "attempts": 0}
    body = (
        f"Bonjour {str(identity.get('first_name','')).strip()},\n\n"
        f"Votre code d'accès au PIP RIASEC Clarté360 est : {code}\n\n"
        f"Ce code est valable {ttl_minutes} minutes.\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\nClarté360"
    )
    ok, message = send_email(smtp, "Votre code d'accès PIP RIASEC Clarté360", body, normalize_email(str(identity["email"])))
    return ok, message, state


def verify_public_code(code: str, state: dict[str, Any]) -> bool:
    if not state or int(state.get("attempts", 0)) >= 6: return False
    try:
        if datetime.now() > datetime.fromisoformat(str(state["expires_at"])): return False
    except Exception:
        return False
    state["attempts"] = int(state.get("attempts", 0)) + 1
    return secrets.compare_digest(code_digest(code.strip()), str(state.get("digest", "")))


def pseudonym_for(participant_id: str) -> str:
    return hashlib.sha256(("clarte360-pip-study:" + participant_id).encode("utf-8")).hexdigest()[:24]


def save_public_study_record(session_state: dict[str, Any]) -> Path:
    participant_id = str(session_state.get("public_participant_id") or session_state.get("passation_id"))
    pip_state = session_state.get("pip_state", {}) or {}
    payload = {
        "schema": "clarte360.pip.public-study.v1",
        "study_id": pseudonym_for(participant_id),
        "passation_id": session_state.get("passation_id"),
        "journey": session_state.get("journey", "PIP_SEUL"),
        "pip_bank_version": pip_state.get("bank_version"),
        "pip_answers": pip_state.get("answers", {}),
        "pip_scoring": session_state.get("pip_scoring", {}),
        "onet_state": session_state.get("onet_state", {}),
        "feeling": session_state.get("feeling", {}),
        "study_consent": bool(session_state.get("study_consent")),
        "completed_at": datetime.now().isoformat(timespec="seconds"),
    }
    path = STUDY_DIR / f"{payload['study_id']}.json"
    _atomic_json(path, payload)
    return path
