import base64
import hashlib
import hmac
import json
import time
from validation import ValidationError, safe_id

TOOL_ID = "preferences-professionnelles"
ALLOWED_ROLES = {"admin", "intervenant"}
ALLOWED_SCOPES = {"PREFERENCES_RUN", "PREFERENCES_RESUME", "PREFERENCES_STATUS", "PREFERENCES_DOCUMENT_READ"}
MAX_TOKEN = 8192
MAX_LIFETIME_SECONDS = 7 * 86400


def _b64d(value):
    return base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))


def verify_launch_token(token, secret, now=None):
    if not token or len(token) > MAX_TOKEN or "." not in token:
        raise ValidationError("Jeton Hub invalide.")
    payload_b64, signature_b64 = token.rsplit(".", 1)
    expected = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    try:
        received = _b64d(signature_b64)
    except Exception:
        raise ValidationError("Signature Hub invalide.")
    if not hmac.compare_digest(expected, received):
        raise ValidationError("Signature Hub invalide.")
    try:
        payload = json.loads(_b64d(payload_b64).decode("utf-8"))
    except Exception:
        raise ValidationError("Contenu du jeton Hub invalide.")
    if not isinstance(payload, dict) or payload.get("tool_id") != TOOL_ID:
        raise ValidationError("Outil Hub incompatible.")
    if payload.get("hub_source") not in {"GESTION_ACTIONS_I9", "GESTION_ACTIONS_I9_H1"}:
        raise ValidationError("Source Hub incompatible.")
    if payload.get("role") not in ALLOWED_ROLES:
        raise ValidationError("Rôle prescripteur non autorisé.")
    for key in ("beneficiary_id", "action_id", "participant_id", "prescription_id"):
        safe_id(payload.get(key), key)
    scopes = payload.get("scopes", [])
    if not isinstance(scopes, list) or "PREFERENCES_RUN" not in scopes or any(x not in ALLOWED_SCOPES for x in scopes):
        raise ValidationError("Droits Hub invalides.")
    current = int(time.time() if now is None else now)
    try:
        exp = int(payload.get("exp", 0))
        iat = int(payload.get("iat", 0))
    except Exception:
        raise ValidationError("Dates du jeton Hub invalides.")
    if exp <= current or iat > current + 300 or exp <= iat or exp - iat > MAX_LIFETIME_SECONDS:
        raise ValidationError("Jeton Hub expiré ou incohérent.")
    return payload


def status_event(payload, status, document_ref=None):
    if status not in {"opened", "in_progress", "completed", "error", "expired"}:
        raise ValidationError("Statut Hub invalide.")
    out = {
        "tool_id": TOOL_ID,
        "status": status,
        "prescription_id": safe_id(payload["prescription_id"], "prescription_id"),
        "beneficiary_id": safe_id(payload["beneficiary_id"], "beneficiary_id"),
        "action_id": safe_id(payload["action_id"], "action_id"),
        "participant_id": safe_id(payload["participant_id"], "participant_id"),
    }
    if document_ref:
        out["document_ref"] = safe_id(document_ref, "document_ref")
    return out
