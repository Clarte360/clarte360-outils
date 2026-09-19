from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.framework.config import PERSISTENT_DATA_DIR
from clarte360_pip.framework.validation import (
    ValidationError, validate_epoch_window, validate_safe_id, validate_string_list,
    validate_person_name, validate_optional_short_text,
)

TOOL_ID = "pip-riasec-onet"
OUTBOX_SCHEMA = "clarte360.pip.gestion-actions.event.v1"
OUTBOUND_CONTRACT_VERSION = "PIP-GA-OUTBOUND-1.0"
ALLOWED_SCOPES = {"PIP_RUN", "PIP_RESUME", "PIP_STATUS", "PIP_RESULT_READ"}
ALLOWED_EVENT_TYPES = {
    "CONSULTE", "EN_COURS", "TERMINE", "ERREUR",
    "CONTACT_EMAIL_VERIFIED", "CONTACT_UPDATED", "CALLBACK_REQUESTED",
}
PUBLIC_CRM_EVENT_TYPES = {"CONTACT_EMAIL_VERIFIED", "CONTACT_UPDATED", "CALLBACK_REQUESTED"}
PUBLIC_CRM_FORBIDDEN_KEYS = {
    "beneficiary_id", "action_id", "participant_id", "prescription_id",
    "study_id", "study_pseudonym", "pseudonym", "passation_id",
    "scores", "score", "holland_code", "pip_answers", "onet_answers",
    "answers", "responses", "report", "report_ref",
}


def _find_forbidden_public_crm_key(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in PUBLIC_CRM_FORBIDDEN_KEYS:
                return str(key)
            found = _find_forbidden_public_crm_key(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_forbidden_public_crm_key(nested)
            if found:
                return found
    return None


class LaunchTokenError(ValueError):
    """Raised when a Gestion des actions launch token is invalid or expired."""


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except Exception as exc:
        raise LaunchTokenError("Jeton de lancement illisible.") from exc


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_launch_token(token: str, signing_key: str, now_epoch: int | None = None) -> LaunchContext:
    if not token or "." not in token or len(token) > 8192:
        raise LaunchTokenError("Jeton de lancement manquant ou invalide.")
    if not signing_key or len(signing_key.strip()) < 24:
        raise LaunchTokenError("Clé de validation du connecteur non configurée.")
    try:
        payload_part, signature_part = token.split(".", 1)
        if not payload_part or not signature_part:
            raise LaunchTokenError("Jeton de lancement incomplet.")
        expected = hmac.new(signing_key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
        supplied = _b64url_decode(signature_part)
    except (UnicodeError, ValueError) as exc:
        raise LaunchTokenError("Jeton de lancement illisible.") from exc
    if not hmac.compare_digest(expected, supplied):
        raise LaunchTokenError("Signature du jeton de lancement invalide.")
    try:
        decoded = _b64url_decode(payload_part)
        if len(decoded) > 16_384:
            raise LaunchTokenError("Contenu du jeton de lancement trop volumineux.")
        payload = json.loads(decoded.decode("utf-8"))
    except LaunchTokenError:
        raise
    except Exception as exc:
        raise LaunchTokenError("Contenu du jeton de lancement invalide.") from exc
    if not isinstance(payload, dict):
        raise LaunchTokenError("Contenu du jeton de lancement invalide.")
    try:
        iat, exp = validate_epoch_window(payload.get("iat"), payload.get("exp"), now_epoch=now_epoch)
        beneficiary_id = validate_safe_id(payload.get("beneficiary_id"), "beneficiary_id")
        action_id = validate_safe_id(payload.get("action_id"), "action_id")
        prescription_id = validate_safe_id(payload.get("prescription_id"), "prescription_id")
        participant_id = validate_safe_id(payload.get("participant_id"), "participant_id", required=False)
        beneficiary_first_name = validate_person_name(payload.get("beneficiary_first_name"), "Prénom bénéficiaire") if payload.get("beneficiary_first_name") not in (None, "") else None
        beneficiary_last_name = validate_person_name(payload.get("beneficiary_last_name"), "Nom bénéficiaire") if payload.get("beneficiary_last_name") not in (None, "") else None
        action_number = validate_optional_short_text(payload.get("action_number"), "Numéro d'action") if payload.get("action_number") not in (None, "") else None
        action_title = validate_optional_short_text(payload.get("action_title"), "Intitulé de l'action") if payload.get("action_title") not in (None, "") else None
        rights_raw = payload.get("scopes", payload.get("rights", []))
        rights = validate_string_list(rights_raw, "Droits/scopes", allowed=ALLOWED_SCOPES, max_items=10)
        if "PIP_RUN" not in rights:
            raise ValidationError("Le jeton ne contient pas le droit PIP_RUN.")
        tool_id = payload.get("tool_id")
        if tool_id is not None and str(tool_id) != TOOL_ID:
            raise ValidationError("Ce lien de lancement est destiné à un autre outil.")
        hub_source = payload.get("hub_source")
        if hub_source is not None and str(hub_source) not in {"GESTION_ACTIONS_I9", "GESTION_ACTIONS_I9_H1"}:
            raise ValidationError("Source Hub du jeton non reconnue.")
    except ValidationError as exc:
        raise LaunchTokenError(str(exc)) from exc
    ctx = LaunchContext(
        mode=RunMode.ACCOMPANIMENT,
        beneficiary_id=beneficiary_id,
        action_id=action_id,
        participant_id=participant_id,
        prescription_id=prescription_id,
        beneficiary_first_name=beneficiary_first_name,
        beneficiary_last_name=beneficiary_last_name,
        action_number=action_number,
        action_title=action_title,
        rights=rights,
        raw={
            "token_version": payload.get("v", 1), "iat": iat, "exp": exp,
            "tool_id": str(tool_id or TOOL_ID),
            "hub_source": str(hub_source or "GESTION_ACTIONS_I9"),
            "return_mode": str(payload.get("return_mode") or "OUTBOX"),
        },
    )
    ctx.validate()
    return ctx


def build_launch_token(payload: Mapping[str, Any], signing_key: str) -> str:
    raw = _canonical_json(payload)
    payload_part = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(signing_key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    signature_part = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{payload_part}.{signature_part}"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _event_id(event_type: str, payload: Mapping[str, Any]) -> str:
    # Content-derived idempotency: identical logical events produce the same key.
    raw = event_type.encode("utf-8") + b"\0" + _canonical_json(payload)
    return hashlib.sha256(raw).hexdigest()[:32]


def _outbox_root() -> Path:
    return PERSISTENT_DATA_DIR / "connector_outbox" / "gestion_actions"


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def persist_report_document(passation_id: str, file_name: str, content: bytes) -> dict[str, Any]:
    passation_id = validate_safe_id(passation_id, "passation_id") or ""
    safe_name = Path(file_name).name
    if not safe_name.lower().endswith(".pdf"):
        raise ValueError("Le document transmis doit être un PDF.")
    folder = PERSISTENT_DATA_DIR / "reports" / passation_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_name
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.replace(path)
    digest = hashlib.sha256(content).hexdigest()
    return {
        "file_name": safe_name,
        "mime_type": "application/pdf",
        "sha256": digest,
        "size_bytes": len(content),
        "storage_ref": str(path.relative_to(PERSISTENT_DATA_DIR)),
    }


@dataclass(frozen=True)
class GestionActionsPort:
    """PIP-side connector boundary. Gestion des Actions remains the source of truth.

    Jalon G deliberately keeps delivery asynchronous: every event is first committed to a
    durable, idempotent outbox. A separate Hub-side/worker transport may acknowledge it later.
    This makes PIP resilient when Gestion des Actions is unavailable.
    """

    signing_key: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.signing_key and self.signing_key.strip())

    def resolve_launch(self, token: str) -> LaunchContext:
        if not self.enabled:
            raise LaunchTokenError("Connecteur Gestion des actions non configuré.")
        return verify_launch_token(token, self.signing_key or "")

    def publish_event(self, event_type: str, payload: dict[str, Any]) -> Path:
        if event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError("Type d'événement PIP non autorisé.")
        if not isinstance(payload, dict) or len(payload) > 80:
            raise ValueError("Payload connecteur invalide.")
        if event_type in PUBLIC_CRM_EVENT_TYPES:
            forbidden = _find_forbidden_public_crm_key(payload)
            if forbidden:
                raise ValueError(f"Événement CRM PUBLIC contenant une clé interdite: {forbidden}")
        else:
            for field in ("beneficiary_id", "action_id", "prescription_id", "passation_id", "participant_id"):
                if payload.get(field) is not None:
                    validate_safe_id(payload.get(field), field, required=False)
        event_id = _event_id(event_type, payload)
        pending = _outbox_root() / "pending" / f"{event_id}.json"
        delivered = _outbox_root() / "delivered" / f"{event_id}.json"
        if delivered.exists():
            return delivered
        if pending.exists():
            return pending
        envelope = {
            "schema": OUTBOX_SCHEMA,
            "event_id": event_id,
            "idempotency_key": event_id,
            "event_type": event_type,
            "tool_id": TOOL_ID,
            "contract_version": OUTBOUND_CONTRACT_VERSION,
            "created_at": _utcnow(),
            "status": "PENDING",
            "attempts": 0,
            "last_attempt_at": None,
            "last_error": None,
            "payload": payload,
        }
        _atomic_json(pending, envelope)
        audit = _outbox_root() / "events.jsonl"
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n")
        return pending

    def signed_delivery_headers(self, envelope: Mapping[str, Any]) -> dict[str, str]:
        """Build HMAC headers for a future server-to-server delivery worker.

        The secret is never put in the URL, payload or logs. Transport remains outside
        Streamlit; the outbox is safe even when the Hub is unavailable.
        """
        if not self.enabled:
            raise LaunchTokenError("Clé HMAC du connecteur non configurée pour l'envoi serveur-à-serveur.")
        body = _canonical_json(envelope)
        signature = hmac.new((self.signing_key or "").encode("utf-8"), body, hashlib.sha256).hexdigest()
        return {
            "X-Clarte360-Tool": TOOL_ID,
            "X-Clarte360-Event-Id": str(envelope.get("event_id") or ""),
            "X-Clarte360-Signature": f"sha256={signature}",
        }

    def pending_events(self) -> list[Path]:
        folder = _outbox_root() / "pending"
        return sorted(folder.glob("*.json")) if folder.exists() else []

    def retry_pending(self, sender: Callable[[dict[str, Any]], None], limit: int = 50) -> dict[str, int]:
        """Try pending events without losing them. Sender raises on transport failure."""
        ok = failed = 0
        for path in self.pending_events()[: max(0, int(limit))]:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            envelope["attempts"] = int(envelope.get("attempts", 0)) + 1
            envelope["last_attempt_at"] = _utcnow()
            try:
                sender(envelope)
            except Exception as exc:
                envelope["status"] = "PENDING"
                envelope["last_error"] = str(exc)[:500]
                _atomic_json(path, envelope)
                failed += 1
                continue
            envelope["status"] = "DELIVERED"
            envelope["delivered_at"] = _utcnow()
            envelope["last_error"] = None
            target = _outbox_root() / "delivered" / path.name
            _atomic_json(target, envelope)
            path.unlink(missing_ok=True)
            ok += 1
        return {"delivered": ok, "failed": failed}
