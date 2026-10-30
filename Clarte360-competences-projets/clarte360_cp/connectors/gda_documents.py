"""Authenticated client for the Gestion des Actions document bridge.

The GDA service remains the binary source of truth. This module only transports
bytes in memory and returns stable references and metadata to C&P.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from clarte360_cp.domain.sources import FORBIDDEN_SOURCE_TYPES


class GDAError(RuntimeError):
    """A safe, user-presentable GDA transport or contract error."""


@dataclass(frozen=True)
class GDASettings:
    base_url: str
    timeout_seconds: int = 15
    max_file_bytes: int = 20 * 1024 * 1024
    request_signing_key: str | None = None

    @property
    def configured(self) -> bool:
        return self.base_url.startswith("https://") and bool(self.request_signing_key and self.request_signing_key.strip())


def load_gda_settings(secrets: Mapping[str, Any] | None = None) -> GDASettings:
    try:
        section = secrets.get("GESTION_ACTIONS_CONNECTOR", {}) if secrets else {}
    except Exception:
        section = {}
    if not isinstance(section, Mapping):
        section = {}
    url = str(section.get("API_BASE_URL", "")).strip().rstrip("/")
    try:
        cp_section = secrets.get("COMPETENCES_PROJETS_CONNECTOR", {}) if secrets else {}
    except Exception:
        cp_section = {}
    signing_key = str(cp_section.get("LAUNCH_SIGNING_KEY", "")).strip() if isinstance(cp_section, Mapping) else ""
    try:
        timeout = max(3, min(int(section.get("TIMEOUT_SECONDS", 15)), 60))
        max_bytes = max(1, min(int(section.get("MAX_FILE_MB", 20)), 50)) * 1024 * 1024
    except (TypeError, ValueError):
        timeout, max_bytes = 15, 20 * 1024 * 1024
    return GDASettings(url, timeout, max_bytes, signing_key or None)


def _metadata(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise GDAError("GDA a renvoyé une référence documentaire illisible.")
    required = ("source_ref", "source_kind", "source_version", "mime_type", "size_bytes", "sha256")
    if any(key not in item for key in required):
        raise GDAError("GDA a renvoyé une référence documentaire incomplète.")
    kind = str(item["source_kind"]).upper()
    if kind in FORBIDDEN_SOURCE_TYPES or kind in {"ONET_REPORT", "PIP_REPORT_PUBLIC"}:
        raise GDAError("Ce type de document n’est pas admis dans Compétences & Projets.")
    digest = str(item["sha256"]).lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise GDAError("L’empreinte du document GDA est invalide.")
    try:
        size = int(item["size_bytes"])
    except (TypeError, ValueError) as exc:
        raise GDAError("La taille du document GDA est invalide.") from exc
    if size < 0:
        raise GDAError("La taille du document GDA est invalide.")
    if item.get("created_by_role") is not None:
        role = str(item["created_by_role"])
        if role not in {"BENEFICIAIRE", "ACCOMPAGNATEUR", "ADMINISTRATEUR"}:
            raise GDAError("Le rôle du déposant transmis par GDA est invalide.")
    if item.get("created_by_ref") is not None:
        actor_ref = str(item["created_by_ref"])
        if not actor_ref or len(actor_ref) > 160:
            raise GDAError("La référence du déposant transmise par GDA est invalide.")
    return dict(item)


def renew_session_launch_token(ctx, signing_key: str, *, now: int | None = None, valid_seconds: int = 900) -> str:
    """Re-sign the already authenticated server-side session for GDA live checks.

    The original launch is still verified on session creation. This short token
    is kept only in server session state; GDA rechecks prescription and live
    assignments on every API request, so revocation takes effect on rerun.
    """
    from datetime import datetime, timezone
    key = str(signing_key or "").strip()
    if len(key) < 24:
        raise GDAError("Clé du connecteur GDA non configurée.")
    issued = int(now if now is not None else datetime.now(timezone.utc).timestamp())
    ttl = max(60, min(int(valid_seconds), 900))
    payload = {
        "v": int(ctx.token_version), "iat": issued, "exp": issued + ttl,
        "beneficiary_id": str(ctx.beneficiary_id), "action_id": str(ctx.action_id),
        "action_no": str(ctx.action_no or ""),
        "prescription_id": str(ctx.prescription_id), "participant_id": str(ctx.participant_id or ""),
        "tool_id": "COMPETENCES_PROJETS", "hub_source": "GESTION_ACTIONS", "scope_vocab": "CP_V1",
        "actor_role": ctx.actor_role.value, "actor_id": str(ctx.actor_id), "scopes": list(ctx.scopes),
    }
    part = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(key.encode(), part.encode(), hashlib.sha256).digest()
    return part + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")


class GDADocumentClient:
    """Small JSON transport; launch token is never logged or put in a URL."""

    def __init__(self, settings: GDASettings, launch_token: str, *, opener=None):
        if not settings.configured:
            raise GDAError("Le connecteur documentaire Gestion des Actions n’est pas configuré.")
        if not launch_token or len(launch_token) > 8192:
            raise GDAError("Le lien Gestion des Actions a expiré. Revenez depuis votre espace pour le renouveler.")
        self.settings, self.launch_token = settings, launch_token
        self.opener = opener or urllib.request.urlopen

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time.time()))
        body_hash = hashlib.sha256(body).hexdigest()
        signable = f"POST\n{path}\n{timestamp}\n{body_hash}".encode("utf-8")
        signature = hmac.new((self.settings.request_signing_key or "").encode("utf-8"), signable, hashlib.sha256).hexdigest()
        req = urllib.request.Request(
            self.settings.base_url + path, data=body, method="POST",
            headers={"Authorization": "Bearer " + self.launch_token,
                     "Content-Type": "application/json", "Accept": "application/json",
                     "X-CP-Timestamp": timestamp, "X-CP-Signature": signature},
        )
        try:
            with self.opener(req, timeout=self.settings.timeout_seconds) as response:
                raw = response.read(self.settings.max_file_bytes * 2 + 65536)
                if len(raw) > self.settings.max_file_bytes * 2 + 65535:
                    raise GDAError("La réponse Gestion des Actions dépasse la taille autorisée.")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise GDAError("Accès refusé ou expiré. Revenez dans Gestion des Actions et rouvrez le dossier.") from exc
            if exc.code == 404:
                raise GDAError("Le service documentaire Gestion des Actions n’est pas encore disponible.") from exc
            raise GDAError("Gestion des Actions est temporairement indisponible.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GDAError("Impossible de joindre Gestion des Actions. Réessayez sans perdre votre travail.") from exc
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GDAError("Gestion des Actions a renvoyé une réponse invalide.") from exc
        if not isinstance(result, dict):
            raise GDAError("Gestion des Actions a renvoyé une réponse invalide.")
        if result.get("error_code"):
            code = str(result["error_code"])
            messages = {
                "NOT_FOUND": "Le document n’est plus disponible dans l’espace partagé.",
                "FORBIDDEN": "Vous n’avez pas accès à ce document dans le dossier courant.",
                "CONTEXT_MISMATCH": "Le document ne correspond pas au dossier ouvert.",
                "EXPIRED": "La prescription est terminée ou a expiré. Revenez dans Gestion des Actions pour vérifier le dossier.",
                "NOT_PUBLISHED": "Ce document n’est pas publié dans l’espace partagé.",
                "CONFLICT": "La référence documentaire a changé. Actualisez la liste.",
            }
            raise GDAError(messages.get(code, "Gestion des Actions a refusé cette opération."))
        return result

    def list_sources(self) -> list[dict[str, Any]]:
        result = self._post("/api/cp/v1/sources/list", {"tool_id": "COMPETENCES_PROJETS"})
        rows = result.get("sources")
        if not isinstance(rows, list):
            raise GDAError("L’inventaire documentaire Gestion des Actions est incomplet.")
        return [_metadata(row) for row in rows]

    def check_session(self) -> bool:
        result = self._post("/api/cp/v1/session/check", {"tool_id": "COMPETENCES_PROJETS"})
        return result.get("authorized") is True

    def get_source(self, source_ref: str) -> tuple[dict[str, Any], bytes]:
        result = self._post("/api/cp/v1/sources/get", {
            "tool_id": "COMPETENCES_PROJETS", "source_ref": str(source_ref),
        })
        metadata = _metadata(result.get("source"))
        encoded = result.get("content_b64")
        if not isinstance(encoded, str):
            raise GDAError("Le document demandé n’a pas été transmis par Gestion des Actions.")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise GDAError("Le contenu transmis par Gestion des Actions est invalide.") from exc
        if len(data) != int(metadata["size_bytes"]) or hashlib.sha256(data).hexdigest() != metadata["sha256"]:
            raise GDAError("L’intégrité du document n’a pas pu être vérifiée. Il n’a pas été importé.")
        if len(data) > self.settings.max_file_bytes:
            raise GDAError("Le document dépasse la taille autorisée par le connecteur.")
        return metadata, data

    def put_unlinked(self, display_name: str, data: bytes, *, mime_type: str | None = None) -> dict[str, Any]:
        if not data or len(data) > self.settings.max_file_bytes:
            raise GDAError("Choisissez un fichier non vide, dans la limite autorisée.")
        safe_name = str(display_name or "").replace("\\", "/").split("/")[-1].strip()
        if not safe_name or len(safe_name) > 180:
            raise GDAError("Le nom du fichier n’est pas accepté.")
        mime = (mime_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream").strip()
        result = self._post("/api/cp/v1/sources/put", {
            "tool_id": "COMPETENCES_PROJETS", "display_name": safe_name,
            "mime_type": mime, "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content_b64": base64.b64encode(data).decode("ascii"),
            "association": None,
        })
        return _metadata(result.get("source"))

    def return_finalized(self, event: dict[str, Any]) -> dict[str, Any]:
        result = self._post("/api/cp/v1/deliverables/ready", event)
        receipt = result.get("receipt")
        if not isinstance(receipt, dict) or receipt.get("status") not in {"ACCEPTED", "REPLAYED"}:
            raise GDAError("Gestion des Actions n’a pas confirmé la remise du livrable.")
        return receipt
