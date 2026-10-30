"""CP_V1 signed launch builder to install in the Gestion des Actions source."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from db import one
from services import trainer_action_authorized

TRAINER_SCOPES = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_SOURCE_GDA_READ",
                  "CP_SOURCE_MANUAL_IMPORT", "CP_VALIDATE", "CP_PUBLISH", "CP_FINALIZE", "CP_DELIVERABLE_RETURN"]
BENEFICIARY_SCOPES = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT",
                      "CP_BENEFICIARY_VALIDATE", "CP_DOCUMENT_READ_PUBLISHED"]


def build_cp_launch(engine, prescription_id, actor_role, actor_id, signing_key, *, valid_seconds=900):
    role = str(actor_role or "").upper()
    actor = str(actor_id or "")
    if len(str(signing_key or "").strip()) < 24:
        raise ValueError("Secret du connecteur Compétences & Projets non configuré.")
    if role not in {"ACCOMPAGNATEUR", "BENEFICIAIRE"} or not actor:
        raise PermissionError("Rôle ou compte non autorisé pour Compétences & Projets.")
    row = one(engine, """SELECT tp.*, tc.base_url, tc.active tool_active, tc.prescription_allowed
        FROM tool_prescriptions tp JOIN tool_catalog tc ON tc.id=tp.tool_id
        WHERE tp.prescription_id=:p AND tc.tool_code='COMPETENCES_PROJETS'""", {"p": prescription_id})
    if not _prescription_open(row):
        raise ValueError("Prescription Compétences & Projets indisponible.")
    if role == "ACCOMPAGNATEUR":
        trainer = one(engine, "SELECT id,active FROM trainers WHERE id=:i", {"i": actor})
        if not trainer or not trainer.get("active") or not trainer_action_authorized(engine, actor, row["action_id"]):
            raise PermissionError("L’intervenant n’est pas affecté à cette action.")
        scopes = TRAINER_SCOPES
    else:
        if actor != str(row["beneficiary_id"]):
            raise PermissionError("Le bénéficiaire ne peut ouvrir que son propre dossier.")
        link = one(engine, "SELECT id FROM participants WHERE id=:p AND action_id=:a AND beneficiary_id=:b AND active=1",
                   {"p": row.get("participant_id"), "a": row["action_id"], "b": row["beneficiary_id"]})
        if not link:
            raise PermissionError("Le bénéficiaire n’est plus rattaché à cette action.")
        scopes = BENEFICIARY_SCOPES
    now = int(time.time())
    ttl = max(60, min(int(valid_seconds or 900), 900))
    payload = {
        "v": 1, "iat": now, "exp": now + ttl,
        "beneficiary_id": str(row["beneficiary_id"]), "action_id": str(row["action_id"]),
        "prescription_id": str(row["prescription_id"]), "participant_id": str(row.get("participant_id") or ""),
        "tool_id": "COMPETENCES_PROJETS", "hub_source": "GESTION_ACTIONS", "scope_vocab": "CP_V1",
        "actor_role": role, "actor_id": actor, "scopes": scopes,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    part = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    signature = hmac.new(str(signing_key).encode(), part.encode(), hashlib.sha256).digest()
    token = part + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")
    base = str(row.get("base_url") or "").strip()
    if not base.startswith("https://"):
        raise ValueError("URL HTTPS de Compétences & Projets non configurée.")
    split = urlsplit(base)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.update({"mode": "accompagnement", "launch": token})
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), ""))


def build_cp_admin_upload_launch(engine, prescription_id, admin_id, signing_key, *, valid_seconds=900):
    """Create a separate C&P upload-only link with no case read capability."""
    if len(str(signing_key or "").strip()) < 24:
        raise ValueError("Secret du connecteur Compétences & Projets non configuré.")
    row = one(engine, """SELECT tp.*, tc.base_url, tc.active tool_active, tc.prescription_allowed
        FROM tool_prescriptions tp JOIN tool_catalog tc ON tc.id=tp.tool_id
        WHERE tp.prescription_id=:p AND tc.tool_code='COMPETENCES_PROJETS'""", {"p": prescription_id})
    admin = one(engine, "SELECT id,active FROM admins WHERE id=:i", {"i": admin_id})
    if not _prescription_open(row):
        raise ValueError("Prescription Compétences & Projets indisponible.")
    if not admin or not admin.get("active"):
        raise PermissionError("Compte administrateur inactif ou inexistant.")
    now = int(time.time()); ttl = max(60, min(int(valid_seconds or 900), 900))
    payload = {
        "v": 1, "iat": now, "exp": now + ttl,
        "beneficiary_id": str(row["beneficiary_id"]), "action_id": str(row["action_id"]),
        "prescription_id": str(row["prescription_id"]), "participant_id": str(row.get("participant_id") or ""),
        "tool_id": "COMPETENCES_PROJETS", "hub_source": "GESTION_ACTIONS", "scope_vocab": "CP_V1",
        "actor_role": "ADMINISTRATEUR", "actor_id": str(admin["id"]),
        "scopes": ["CP_SOURCE_ADMIN_PUT"],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    part = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    signature = hmac.new(str(signing_key).encode(), part.encode(), hashlib.sha256).digest()
    token = part + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")
    base = str(row.get("base_url") or "").strip()
    if not base.startswith("https://"):
        raise ValueError("URL HTTPS de Compétences & Projets non configurée.")
    split = urlsplit(base); query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.update({"mode": "upload_only", "launch": token})
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), ""))


def _prescription_open(row):
    # This helper is used only to open/manage an already existing prescription.
    # prescription_allowed gates creation in the GDA UI and must not revoke access
    # to a case that was validly prescribed earlier.
    if not row or str(row.get("status") or "").upper() not in {"A_FAIRE", "ENVOYE", "CONSULTE", "EN_COURS"} or not row.get("tool_active"):
        return False
    expires = row.get("expires_at")
    if expires:
        try:
            deadline = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if deadline <= datetime.now(timezone.utc):
                return False
        except ValueError:
            return False
    return True
