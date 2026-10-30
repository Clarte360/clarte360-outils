from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping

from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.domain.launch import (
    ACCOMPAGNATEUR_SCOPES, BENEFICIAIRE_SCOPES, HUB_SOURCE, SCOPE_VOCAB, TOOL_CODE, LaunchContext,
)
from clarte360_cp.framework.validation import ValidationError, validate_epoch_window, validate_safe_id, validate_string_list


class LaunchTokenError(ValueError):
    pass


@dataclass(frozen=True)
class AdminUploadContext:
    beneficiary_id: str
    action_id: str
    prescription_id: str
    participant_id: str | None
    actor_id: str
    scopes: tuple[str, ...]
    iat: int
    exp: int


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except Exception as exc:
        raise LaunchTokenError("Jeton de lancement illisible.") from exc


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_launch_token(payload: Mapping[str, Any], signing_key: str) -> str:
    raw = _canonical_json(payload)
    payload_part = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(signing_key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    signature_part = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{payload_part}.{signature_part}"


def verify_launch_token(token: str, signing_key: str, *, now_epoch: int | None = None) -> LaunchContext:
    if not token or "." not in token or len(token) > 8192:
        raise LaunchTokenError("Jeton de lancement manquant ou invalide.")
    if not signing_key or len(signing_key.strip()) < 24:
        raise LaunchTokenError("Clé de validation du connecteur non configurée.")
    try:
        payload_part, signature_part = token.split(".", 1)
        expected = hmac.new(signing_key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
        supplied = _b64url_decode(signature_part)
    except Exception as exc:
        raise LaunchTokenError("Jeton de lancement illisible.") from exc
    if not hmac.compare_digest(expected, supplied):
        raise LaunchTokenError("Signature du jeton de lancement invalide.")
    try:
        raw = _b64url_decode(payload_part)
        if len(raw) > 16_384:
            raise LaunchTokenError("Contenu du jeton trop volumineux.")
        payload = json.loads(raw.decode("utf-8"))
    except LaunchTokenError:
        raise
    except Exception as exc:
        raise LaunchTokenError("Contenu du jeton de lancement invalide.") from exc
    if not isinstance(payload, dict):
        raise LaunchTokenError("Contenu du jeton de lancement invalide.")

    forbidden = {"beneficiary", "nom", "prenom", "first_name", "last_name", "email", "phone", "telephone"}
    if forbidden.intersection(payload):
        raise LaunchTokenError("Le jeton contient des données nominatives interdites.")
    try:
        iat, exp = validate_epoch_window(payload.get("iat"), payload.get("exp"), now_epoch=now_epoch, max_lifetime_seconds=900)
        beneficiary_id = validate_safe_id(payload.get("beneficiary_id"), "beneficiary_id")
        action_id = validate_safe_id(payload.get("action_id"), "action_id")
        action_no = str(payload.get("action_no") or "").strip()
        if len(action_no) > 64 or any(ord(ch) < 32 for ch in action_no):
            raise ValidationError("Référence d’action invalide.")
        prescription_id = validate_safe_id(payload.get("prescription_id"), "prescription_id")
        participant_id = validate_safe_id(payload.get("participant_id"), "participant_id", required=False)
        actor_id = validate_safe_id(payload.get("actor_id"), "actor_id")
        role = ActorRole(str(payload.get("actor_role")))
        if payload.get("tool_id") != TOOL_CODE:
            raise ValidationError("Ce lien est destiné à un autre outil.")
        if payload.get("scope_vocab") != SCOPE_VOCAB:
            raise ValidationError("Vocabulaire de scopes non supporté.")
        if payload.get("hub_source") != HUB_SOURCE:
            raise ValidationError("Source Hub non reconnue.")
        allowed = ACCOMPAGNATEUR_SCOPES if role is ActorRole.ACCOMPAGNATEUR else BENEFICIAIRE_SCOPES
        scopes = validate_string_list(payload.get("scopes"), "Scopes", allowed=allowed, max_items=20)
        if "CP_CASE_OPEN" not in scopes:
            raise ValidationError("Le jeton ne contient pas CP_CASE_OPEN.")
    except (ValidationError, ValueError) as exc:
        raise LaunchTokenError(str(exc)) from exc
    return LaunchContext(
        beneficiary_id=beneficiary_id or "", action_id=action_id or "", prescription_id=prescription_id or "",
        participant_id=participant_id, actor_role=role, actor_id=actor_id or "", scopes=scopes,
        action_no=action_no, token_version=int(payload.get("v", 1)), iat=iat, exp=exp,
    )


def verify_admin_upload_token(token: str, signing_key: str, *, now_epoch: int | None = None) -> AdminUploadContext:
    """Verify a separate upload-only GDA admin link; it cannot open a C&P case."""
    if not token or "." not in token or len(token) > 8192:
        raise LaunchTokenError("Lien de dépôt administrateur manquant ou invalide.")
    if not signing_key or len(signing_key.strip()) < 24:
        raise LaunchTokenError("Clé de validation du connecteur non configurée.")
    try:
        payload_part, signature_part = token.split(".", 1)
        expected = hmac.new(signing_key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
        supplied = _b64url_decode(signature_part)
        raw = _b64url_decode(payload_part)
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise LaunchTokenError("Lien de dépôt administrateur illisible.") from exc
    if not hmac.compare_digest(expected, supplied) or not isinstance(payload, dict) or len(raw) > 16_384:
        raise LaunchTokenError("Signature du lien de dépôt administrateur invalide.")
    now = int(time.time()) if now_epoch is None else int(now_epoch)
    iat, exp = validate_epoch_window(payload.get("iat"), payload.get("exp"), now_epoch=now, max_lifetime_seconds=900)
    if payload.get("tool_id") != TOOL_CODE or payload.get("hub_source") != HUB_SOURCE or payload.get("scope_vocab") != SCOPE_VOCAB:
        raise LaunchTokenError("Lien de dépôt destiné à un autre outil.")
    if payload.get("actor_role") != "ADMINISTRATEUR" or payload.get("scopes") != ["CP_SOURCE_ADMIN_PUT"]:
        raise LaunchTokenError("Ce lien n’autorise que le dépôt documentaire administrateur.")
    forbidden = {"beneficiary", "nom", "prenom", "first_name", "last_name", "email", "phone", "telephone"}
    if forbidden.intersection(payload):
        raise LaunchTokenError("Le lien de dépôt contient des données nominatives interdites.")
    try:
        values = {
            "beneficiary_id": validate_safe_id(payload.get("beneficiary_id"), "beneficiary_id"),
            "action_id": validate_safe_id(payload.get("action_id"), "action_id"),
            "prescription_id": validate_safe_id(payload.get("prescription_id"), "prescription_id"),
            "participant_id": validate_safe_id(payload.get("participant_id"), "participant_id", required=False),
            "actor_id": validate_safe_id(payload.get("actor_id"), "actor_id"),
        }
    except ValidationError as exc:
        raise LaunchTokenError(str(exc)) from exc
    return AdminUploadContext(**values, scopes=("CP_SOURCE_ADMIN_PUT",), iat=iat, exp=exp)
