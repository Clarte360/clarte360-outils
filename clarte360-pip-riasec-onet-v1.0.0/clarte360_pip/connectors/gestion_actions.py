from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.framework.config import PERSISTENT_DATA_DIR
from clarte360_pip.framework.validation import (
    ValidationError, validate_epoch_window, validate_safe_id, validate_string_list,
)

TOOL_ID = "pip-riasec-onet"
ALLOWED_SCOPES = {"PIP_RUN", "PIP_RESUME", "PIP_STATUS", "PIP_RESULT_READ"}


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
    """Verify a compact HMAC-SHA256 token produced by Gestion des actions.

    Backward compatible with the existing PIP connector contract (`rights`, `exp`) and
    ready for the I9-H1 common vocabulary (`scopes`, `tool_id`, `hub_source`).
    No dossier identifier is ever accepted outside the signed payload.
    """
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

        # I9-H1 uses a common scopes vocabulary; the legacy PIP field `rights` remains accepted.
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
        rights=rights,
        raw={
            "token_version": payload.get("v", 1),
            "iat": iat,
            "exp": exp,
            "tool_id": str(tool_id or TOOL_ID),
            "hub_source": str(hub_source or "GESTION_ACTIONS_I9"),
            "return_mode": str(payload.get("return_mode") or "OUTBOX"),
        },
    )
    ctx.validate()
    return ctx


def build_launch_token(payload: Mapping[str, Any], signing_key: str) -> str:
    """Test/helper implementation of the shared token contract; never embeds a real key."""
    raw = _canonical_json(payload)
    payload_part = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(signing_key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    signature_part = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{payload_part}.{signature_part}"


@dataclass(frozen=True)
class GestionActionsPort:
    """PIP-side connector boundary. Gestion des actions remains identity source of truth."""

    signing_key: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.signing_key and self.signing_key.strip())

    def resolve_launch(self, token: str) -> LaunchContext:
        if not self.enabled:
            raise LaunchTokenError("Connecteur Gestion des actions non configuré.")
        return verify_launch_token(token, self.signing_key or "")

    def publish_event(self, event_type: str, payload: dict[str, Any]) -> Path:
        """Write a durable local outbox event pending the future Gestion-actions transport.

        No PII is required: only technical Clarté360 identifiers and minimal state.
        """
        allowed = {"CONSULTE", "EN_COURS", "TERMINE", "ERREUR"}
        if event_type not in allowed:
            raise ValueError("Type d'événement PIP non autorisé.")
        if not isinstance(payload, dict) or len(payload) > 50:
            raise ValueError("Payload connecteur invalide.")
        for field in ("beneficiary_id", "action_id", "prescription_id"):
            if payload.get(field) is not None:
                validate_safe_id(payload.get(field), field)
        if payload.get("participant_id") is not None:
            validate_safe_id(payload.get("participant_id"), "participant_id", required=False)
        outbox = PERSISTENT_DATA_DIR / "connector_outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        path = outbox / "gestion_actions_events.jsonl"
        event = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        return path
