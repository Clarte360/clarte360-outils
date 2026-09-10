from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.framework.config import PERSISTENT_DATA_DIR

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")


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


def _safe_id(value: str | None, field: str) -> str:
    if not value or not _SAFE_ID.fullmatch(str(value)):
        raise LaunchTokenError(f"Identifiant de lancement invalide : {field}.")
    return str(value)


def verify_launch_token(token: str, signing_key: str, now_epoch: int | None = None) -> LaunchContext:
    """Verify a compact HMAC-SHA256 token produced by Gestion des actions.

    Format: base64url(canonical-json-payload).base64url(hmac_sha256(payload_part)).
    The token is intentionally simple, deterministic and dependency-free so the future
    Gestion des actions connector can implement the same contract.
    """
    if not token or "." not in token:
        raise LaunchTokenError("Jeton de lancement manquant ou invalide.")
    if not signing_key or len(signing_key.strip()) < 24:
        raise LaunchTokenError("Clé de validation du connecteur non configurée.")

    payload_part, signature_part = token.split(".", 1)
    expected = hmac.new(signing_key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    supplied = _b64url_decode(signature_part)
    if not hmac.compare_digest(expected, supplied):
        raise LaunchTokenError("Signature du jeton de lancement invalide.")

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except Exception as exc:
        raise LaunchTokenError("Contenu du jeton de lancement invalide.") from exc
    if not isinstance(payload, dict):
        raise LaunchTokenError("Contenu du jeton de lancement invalide.")

    now_epoch = int(datetime.now(timezone.utc).timestamp()) if now_epoch is None else int(now_epoch)
    try:
        exp = int(payload["exp"])
        iat = int(payload.get("iat", now_epoch))
    except Exception as exc:
        raise LaunchTokenError("Dates du jeton de lancement invalides.") from exc
    if exp < now_epoch:
        raise LaunchTokenError("Ce lien de lancement a expiré.")
    if iat > now_epoch + 300:
        raise LaunchTokenError("Date de création du jeton incohérente.")
    if exp - iat > 7 * 24 * 3600:
        raise LaunchTokenError("Durée de validité du jeton excessive.")

    beneficiary_id = _safe_id(payload.get("beneficiary_id"), "beneficiary_id")
    action_id = _safe_id(payload.get("action_id"), "action_id")
    prescription_id = _safe_id(payload.get("prescription_id"), "prescription_id")
    participant = payload.get("participant_id")
    participant_id = _safe_id(participant, "participant_id") if participant else None
    rights_raw = payload.get("rights", [])
    if not isinstance(rights_raw, list) or any(not isinstance(v, str) for v in rights_raw):
        raise LaunchTokenError("Droits du jeton invalides.")

    ctx = LaunchContext(
        mode=RunMode.ACCOMPANIMENT,
        beneficiary_id=beneficiary_id,
        action_id=action_id,
        participant_id=participant_id,
        prescription_id=prescription_id,
        rights=tuple(rights_raw),
        raw={"token_version": payload.get("v", 1), "iat": iat, "exp": exp},
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
        allowed = {"CONSULTE", "EN_COURS", "TERMINE"}
        if event_type not in allowed:
            raise ValueError("Type d'événement PIP non autorisé.")
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
