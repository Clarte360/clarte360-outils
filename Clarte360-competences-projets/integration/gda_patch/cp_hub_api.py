"""Drop-in, loopback-only HTTP bridge for the GDA application.

Install beside GDA's app.py and run behind its HTTPS reverse proxy. The API
validates the signed CP_V1 launch on every request, then rechecks live GDA
prescription, participant, and trainer assignment records. It never exposes a
storage path or accepts a requested C&P business association on upload.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import tomllib
from datetime import datetime, timezone
from uuid import uuid4
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from db import make_engine, one, q, execute, utcnow_iso
from services import DOC_PRIVATE, DEFAULT_ALLOWED_EXTENSIONS, store_document, audit

MAX_UPLOAD = int(os.getenv("CP_GDA_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
SECRET_FILE = Path(os.getenv("CLARTE360_SECRET_FILE", "/opt/clarte360/secrets/secrets.toml"))


def _dbid(value):
    if value in (None, ""):
        return None
    value = str(value)
    return int(value) if value.isdecimal() else value


def _settings():
    data = tomllib.loads(SECRET_FILE.read_text("utf-8"))
    secret = str(data.get("COMPETENCES_PROJETS_CONNECTOR", {}).get("LAUNCH_SIGNING_KEY", ""))
    if len(secret.strip()) < 24:
        raise RuntimeError("CP connector secret is missing or too short")
    return make_engine(data.get("database", {}).get("url")), secret


def _b64decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verify(token, key):
    if not token or len(token) > 8192 or "." not in token:
        raise PermissionError("INVALID_TOKEN")
    part, signature = token.split(".", 1)
    expected = hmac.new(key.encode(), part.encode("ascii"), hashlib.sha256).digest()
    try:
        supplied = _b64decode(signature)
        payload = json.loads(_b64decode(part).decode("utf-8"))
    except Exception as exc:
        raise PermissionError("INVALID_TOKEN") from exc
    if not hmac.compare_digest(expected, supplied) or not isinstance(payload, dict):
        raise PermissionError("INVALID_TOKEN")
    now = int(time.time())
    if payload.get("tool_id") != "COMPETENCES_PROJETS" or payload.get("scope_vocab") != "CP_V1":
        raise PermissionError("INVALID_TOKEN")
    if payload.get("hub_source") != "GESTION_ACTIONS" or int(payload.get("v", 0)) != 1:
        raise PermissionError("INVALID_TOKEN")
    if int(payload.get("iat", 0)) > now + 30 or int(payload.get("exp", 0)) < now or int(payload.get("exp", 0)) - int(payload.get("iat", 0)) > 900:
        raise PermissionError("EXPIRED")
    for field in ("beneficiary_id", "action_id", "prescription_id", "actor_id"):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", str(payload.get(field, ""))):
            raise PermissionError("INVALID_TOKEN")
    if any(k in payload for k in ("beneficiary", "nom", "prenom", "email", "phone", "telephone")):
        raise PermissionError("INVALID_TOKEN")
    role = payload.get("actor_role")
    allowed = {
        "ACCOMPAGNATEUR": {"CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_SOURCE_GDA_READ", "CP_SOURCE_MANUAL_IMPORT", "CP_VALIDATE", "CP_PUBLISH", "CP_FINALIZE", "CP_DELIVERABLE_RETURN"},
        "BENEFICIAIRE": {"CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT", "CP_BENEFICIARY_VALIDATE", "CP_DOCUMENT_READ_PUBLISHED"},
        "ADMINISTRATEUR": {"CP_SOURCE_ADMIN_PUT"},
    }
    scopes = payload.get("scopes")
    if role == "ADMINISTRATEUR":
        if scopes != ["CP_SOURCE_ADMIN_PUT"]:
            raise PermissionError("INVALID_TOKEN")
    elif role not in allowed or not isinstance(scopes, list) or not set(scopes) <= allowed[role] or "CP_CASE_OPEN" not in scopes:
        raise PermissionError("INVALID_TOKEN")
    return payload


def _authorize(engine, ctx, scope):
    if scope not in ctx["scopes"]:
        raise PermissionError("FORBIDDEN")
    pr = one(engine, """SELECT * FROM tool_prescriptions WHERE prescription_id=:p
        AND tool_id=(SELECT id FROM tool_catalog WHERE tool_code='COMPETENCES_PROJETS' LIMIT 1)""", {"p": ctx["prescription_id"]})
    if not pr or str(pr.get("action_id")) != str(ctx["action_id"]) or str(pr.get("beneficiary_id")) != str(ctx["beneficiary_id"]) or str(pr.get("participant_id") or "") != str(ctx.get("participant_id") or "") or str(pr.get("status") or "").upper() not in {"A_FAIRE", "ENVOYE", "CONSULTE", "EN_COURS"}:
        raise PermissionError("CONTEXT_MISMATCH")
    expires = pr.get("expires_at")
    if expires:
        expiry = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= datetime.now(timezone.utc):
            raise PermissionError("EXPIRED")
    if ctx["actor_role"] == "ADMINISTRATEUR":
        admin = one(engine, "SELECT id,active FROM admins WHERE id=:i", {"i": _dbid(ctx["actor_id"])})
        if not admin or not admin.get("active"):
            raise PermissionError("FORBIDDEN")
    elif ctx["actor_role"] == "BENEFICIAIRE":
        if str(ctx["actor_id"]) != str(ctx["beneficiary_id"]):
            raise PermissionError("FORBIDDEN")
        row = one(engine, "SELECT id FROM participants WHERE action_id=:a AND beneficiary_id=:b AND active=1", {"a": _dbid(ctx["action_id"]), "b": _dbid(ctx["beneficiary_id"])})
        if not row:
            raise PermissionError("FORBIDDEN")
    else:
        from services import trainer_action_authorized
        if not trainer_action_authorized(engine, _dbid(ctx["actor_id"]), _dbid(ctx["action_id"])):
            raise PermissionError("FORBIDDEN")
    return pr


def _source_visible_to_actor(row, ctx):
    """Apply GDA audience after dossier-level filtering."""
    audience = str(row.get("audience") or "").upper()
    role = str(ctx.get("actor_role") or "").upper()
    if audience == "ADMIN_ONLY":
        return False
    if role == "BENEFICIAIRE":
        return bool(row.get("visible_to_beneficiary")) and audience != "TRAINER_ONLY"
    # Accompanists assigned to the action can use published beneficiary,
    # trainer, and shared documents. Administrators remain upload-only.
    return role == "ACCOMPAGNATEUR"


def _source_rows(engine, ctx):
    # Only published documents attached to this beneficiary and action are
    # candidates. GDA audience is evaluated for the signed actor below; a
    # single SQL audience filter would hide CLIENT_ONLY uploads from the
    # beneficiary and TRAINER_ONLY sources from the assigned accompanist.
    rows = q(engine, """SELECT dr.*, sf.sha256, sf.size_bytes, sf.mime_type,
        pd.document_kind
        FROM document_references dr JOIN stored_files sf ON sf.id=dr.stored_file_id
        LEFT JOIN prescription_documents pd ON pd.document_reference_id=dr.id
        WHERE dr.action_id=:a AND dr.deleted_at IS NULL AND dr.superseded_at IS NULL
          AND dr.publication_status='PUBLIE' AND dr.beneficiary_id=:b
          AND (dr.participant_id IS NULL OR dr.participant_id=:pp)
        ORDER BY dr.created_at DESC, dr.id DESC""",
        {"a": _dbid(ctx["action_id"]), "b": _dbid(ctx["beneficiary_id"]), "pp": _dbid(ctx.get("participant_id"))})
    output = []
    for row in rows:
        if not _source_visible_to_actor(row, ctx):
            continue
        kind = str(row.get("document_kind") or "").upper()
        category = str(row.get("category") or "").upper()
        if kind == "ONET_REPORT" or category in {"ONET_REPORT", "PIP_PUBLIC_REPORT", "PIP_REPORT_PUBLIC"}:
            continue
        provenance = one(engine, "SELECT actor_role, actor_ref, created_at FROM cp_api_source_provenance WHERE source_ref=:r", {"r": str(row["id"])})
        descriptor = {
            "source_ref": str(row["id"]),
            "source_kind": "PIP_REPORT" if kind == "PIP_REPORT" else "DOCUMENT_NON_ASSOCIE",
            "source_version": str(row.get("version_no") or 1),
            "mime_type": row.get("mime_type") or "application/octet-stream",
            "size_bytes": int(row.get("size_bytes") or 0), "sha256": str(row["sha256"]),
            "display_name": str(row.get("display_name") or "Document"),
            "category": str(row.get("category") or ""), "created_at": row.get("created_at"),
            "publication_status": row.get("publication_status"),
        }
        if provenance:
            descriptor["created_by_role"] = provenance["actor_role"]
            descriptor["created_by_ref"] = provenance["actor_ref"]
            descriptor["created_at"] = provenance["created_at"]
        output.append(descriptor)
    return output


def _deliverable(engine, ctx, body):
    _authorize(engine, ctx, "CP_DELIVERABLE_RETURN")
    if body.get("event_type") != "CP_DELIVERABLE_READY" or body.get("scope") != "CP_DELIVERABLE_RETURN":
        raise ValueError("BAD_REQUEST")
    if str(body.get("action_id")) != str(ctx["action_id"]) or str(body.get("beneficiary_id")) != str(ctx["beneficiary_id"]) or str(body.get("prescription_id")) != str(ctx["prescription_id"]):
        raise PermissionError("CONTEXT_MISMATCH")
    kind = str(body.get("document_kind") or "").upper()
    if kind not in {"PLAN_ACTION_FINAL", "RESULTATS_DETAILLES_FINAL", "SYNTHESE_FINALE"} or body.get("status") != "FINALIZED":
        raise ValueError("BAD_REQUEST")
    if body.get("audience") != "BENEFICIARY_ONLY" or body.get("tool_id") != "COMPETENCES_PROJETS":
        raise ValueError("BAD_REQUEST")
    if body.get("mime_type") != "application/pdf" or not str(body.get("document_version") or "")[:100]:
        raise ValueError("BAD_REQUEST")
    event_id = str(body.get("event_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", event_id):
        raise ValueError("BAD_REQUEST")
    try:
        content = base64.b64decode(body.get("content_b64", ""), validate=True)
    except Exception as exc:
        raise ValueError("INTEGRITY") from exc
    digest = hashlib.sha256(content).hexdigest()
    if (not content or len(content) > MAX_UPLOAD or len(content) != int(body.get("size_bytes", -1))
            or digest != str(body.get("sha256", "")).lower()):
        raise ValueError("INTEGRITY")
    ext = Path(str(body.get("display_name") or "")).suffix.lower()
    if ext != ".pdf" or not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
        raise ValueError("EXTENSION")
    old = one(engine, "SELECT * FROM cp_api_receipts WHERE event_id=:e", {"e": event_id})
    if old:
        if old["sha256"] != digest or old["document_kind"] != kind:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return {"receipt_id": old["receipt_id"], "event_id": event_id,
                "status": "REPLAYED", "document_reference_id": old["document_reference_id"],
                "sha256": digest, "received_at": old["received_at"]}
    rid, stored_digest, _dedup = store_document(
        engine, content, body["display_name"], "C360_CP_DELIVERABLE",
        f"cp:{ctx['actor_role']}:{ctx['actor_id']}", action_id=_dbid(ctx["action_id"]),
        beneficiary_id=_dbid(ctx["beneficiary_id"]), participant_id=_dbid(ctx.get("participant_id")),
        audience=DOC_PRIVATE, visible_to_beneficiary=True,
        allowed_extensions={".pdf", ".docx"},
    )
    if stored_digest != digest:
        raise ValueError("INTEGRITY")
    receipt_id = str(uuid4()); received = utcnow_iso()
    try:
        execute(engine, """INSERT INTO cp_api_receipts(event_id,receipt_id,document_reference_id,document_kind,sha256,received_at)
            VALUES(:e,:r,:d,:k,:h,:n)""", {"e": event_id, "r": receipt_id, "d": rid, "k": kind, "h": digest, "n": received})
    except Exception:
        old = one(engine, "SELECT * FROM cp_api_receipts WHERE event_id=:e", {"e": event_id})
        if not old or old["sha256"] != digest or old["document_kind"] != kind:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return {"receipt_id": old["receipt_id"], "event_id": event_id,
                "status": "REPLAYED", "document_reference_id": old["document_reference_id"],
                "sha256": digest, "received_at": old["received_at"]}
    audit(engine, "CP_DELIVERABLE_RECEIVED", _dbid(ctx["action_id"]),
          f"cp:{ctx['actor_role']}:{ctx['actor_id']}", "tool_prescription", ctx["prescription_id"],
          {"event_id": event_id, "document_kind": kind, "document_reference_id": rid, "sha256": digest})
    return {"receipt_id": receipt_id, "event_id": event_id, "status": "ACCEPTED",
            "document_reference_id": str(rid), "sha256": digest, "received_at": received}


def _read_source(engine, ctx, ref):
    row = next((r for r in _source_rows(engine, ctx) if r["source_ref"] == str(ref)), None)
    if not row:
        raise PermissionError("NOT_FOUND")
    stored = one(engine, """SELECT sf.storage_path FROM document_references dr
        JOIN stored_files sf ON sf.id=dr.stored_file_id WHERE dr.id=:i""", {"i": _dbid(row["source_ref"])})
    if not stored or not Path(stored["storage_path"]).is_file():
        raise FileNotFoundError("NOT_FOUND")
    data = Path(stored["storage_path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise ValueError("INTEGRITY")
    return row, data


class Handler(BaseHTTPRequestHandler):
    server_version = "Clarte360GDA-CP/1"
    engine, signing_key = _settings()

    def log_message(self, *_):
        # Never write bearer token, document name, or body to access logs.
        return

    def _ensure_receipts(self):
        from sqlalchemy import text
        with self.engine.begin() as conn:
            conn.execute(text("""CREATE TABLE IF NOT EXISTS cp_api_receipts (
                event_id TEXT PRIMARY KEY, receipt_id TEXT NOT NULL UNIQUE,
                document_reference_id INTEGER NOT NULL, document_kind TEXT NOT NULL,
                sha256 TEXT NOT NULL, received_at TEXT NOT NULL)"""))

    def _ensure_source_provenance(self):
        from sqlalchemy import text
        with self.engine.begin() as conn:
            conn.execute(text("""CREATE TABLE IF NOT EXISTS cp_api_source_provenance (
                source_ref TEXT PRIMARY KEY, actor_role TEXT NOT NULL,
                actor_ref TEXT NOT NULL, created_at TEXT NOT NULL)"""))

    def _reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path != "/healthz":
            self._reply(404, {"error_code": "NOT_FOUND"}); return
        self._reply(200, {"service": "gda-cp-bridge", "status": "ready"})

    def do_POST(self):
        route = urlparse(self.path).path
        if route not in {"/api/cp/v1/session/check", "/api/cp/v1/sources/list", "/api/cp/v1/sources/get", "/api/cp/v1/sources/put", "/api/cp/v1/deliverables/ready"}:
            self._reply(404, {"error_code": "NOT_FOUND"}); return
        try:
            self._ensure_source_provenance()
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > (MAX_UPLOAD * 2 + 128 * 1024):
                raise ValueError("SIZE")
            raw = self.rfile.read(length)
            timestamp = self.headers.get("X-CP-Timestamp", "")
            supplied_signature = self.headers.get("X-CP-Signature", "")
            try:
                signed_at = int(timestamp)
            except ValueError as exc:
                raise PermissionError("INVALID_REQUEST_SIGNATURE") from exc
            if abs(int(time.time()) - signed_at) > 300:
                raise PermissionError("EXPIRED_REQUEST_SIGNATURE")
            request_hash = hashlib.sha256(raw).hexdigest()
            signable = f"POST\n{route}\n{timestamp}\n{request_hash}".encode("utf-8")
            expected_signature = hmac.new(self.signing_key.encode("utf-8"), signable, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_signature, supplied_signature):
                raise PermissionError("INVALID_REQUEST_SIGNATURE")
            body = json.loads(raw.decode("utf-8"))
            if not isinstance(body, dict) or body.get("tool_id") != "COMPETENCES_PROJETS":
                raise ValueError("BAD_REQUEST")
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                raise PermissionError("INVALID_TOKEN")
            ctx = _verify(auth[7:], self.signing_key)
            if route.endswith("/session/check"):
                if ctx["actor_role"] == "ADMINISTRATEUR":
                    raise PermissionError("FORBIDDEN")
                _authorize(self.engine, ctx, "CP_CASE_READ")
                self._reply(200, {"authorized": True}); return
            if route.endswith("/list"):
                _authorize(self.engine, ctx, "CP_SOURCE_GDA_READ")
                self._reply(200, {"sources": _source_rows(self.engine, ctx)}); return
            if route.endswith("/get"):
                if ctx["actor_role"] == "ACCOMPAGNATEUR":
                    _authorize(self.engine, ctx, "CP_SOURCE_GDA_READ")
                else:
                    _authorize(self.engine, ctx, "CP_DOCUMENT_READ_PUBLISHED")
                metadata, content = _read_source(self.engine, ctx, body.get("source_ref"))
                self._reply(200, {"source": metadata, "content_b64": base64.b64encode(content).decode("ascii")}); return
            if route.endswith("/put"):
                if ctx["actor_role"] == "ACCOMPAGNATEUR":
                    _authorize(self.engine, ctx, "CP_SOURCE_MANUAL_IMPORT")
                elif ctx["actor_role"] == "ADMINISTRATEUR":
                    _authorize(self.engine, ctx, "CP_SOURCE_ADMIN_PUT")
                else:
                    _authorize(self.engine, ctx, "CP_BENEFICIARY_INTERACT")
                if body.get("association") is not None:
                    raise ValueError("ASSOCIATION_FORBIDDEN")
                data = base64.b64decode(body.get("content_b64", ""), validate=True)
                if not data or len(data) > MAX_UPLOAD or len(data) != int(body.get("size_bytes", -1)) or hashlib.sha256(data).hexdigest() != body.get("sha256"):
                    raise ValueError("INTEGRITY")
                ext = Path(str(body.get("display_name") or "")).suffix.lower()
                if ext not in set(DEFAULT_ALLOWED_EXTENSIONS):
                    raise ValueError("EXTENSION")
                participant = one(self.engine, "SELECT id FROM participants WHERE action_id=:a AND beneficiary_id=:b AND active=1 LIMIT 1", {"a": _dbid(ctx["action_id"]), "b": _dbid(ctx["beneficiary_id"])})
                if not participant:
                    raise PermissionError("CONTEXT_MISMATCH")
                rid, digest, _dedup = store_document(self.engine, data, body["display_name"], "C360_CP_SOURCE",
                    f"cp:{ctx['actor_role']}:{ctx['actor_id']}", action_id=_dbid(ctx["action_id"]),
                    beneficiary_id=_dbid(ctx["beneficiary_id"]), participant_id=_dbid(ctx.get("participant_id")) or participant["id"],
                    audience=DOC_PRIVATE, visible_to_beneficiary=True, allowed_extensions=set(DEFAULT_ALLOWED_EXTENSIONS))
                with self.engine.begin() as conn:
                    from sqlalchemy import text
                    params = {"r": str(rid), "role": str(ctx["actor_role"]), "actor": str(ctx["actor_id"]), "created": utcnow_iso()}
                    exists = conn.execute(text("SELECT 1 FROM cp_api_source_provenance WHERE source_ref=:r"), params).first()
                    if not exists:
                        conn.execute(text("""INSERT INTO cp_api_source_provenance
                            (source_ref, actor_role, actor_ref, created_at) VALUES (:r, :role, :actor, :created)"""), params)
                metadata, _ = _read_source(self.engine, ctx, rid)
                self._reply(201, {"source": metadata}); return
            self._ensure_receipts()
            self._reply(200, {"receipt": _deliverable(self.engine, ctx, body)}); return
        except PermissionError as exc:
            code = str(exc)
            status = 401 if code in {"INVALID_TOKEN", "EXPIRED"} else 403
            self._reply(status, {"error_code": code}); return
        except FileNotFoundError:
            self._reply(404, {"error_code": "NOT_FOUND"}); return
        except Exception as exc:
            code = str(exc) if str(exc) in {"INTEGRITY", "SIZE", "EXTENSION", "ASSOCIATION_FORBIDDEN", "IDEMPOTENCY_CONFLICT"} else "BAD_REQUEST"
            self._reply(400, {"error_code": code})


if __name__ == "__main__":
    host = os.getenv("CP_GDA_BIND", "127.0.0.1")
    port = int(os.getenv("CP_GDA_PORT", "8765"))
    ThreadingHTTPServer((host, port), Handler).serve_forever()
