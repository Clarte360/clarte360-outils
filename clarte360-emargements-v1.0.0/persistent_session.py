from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from db import execute, one, q, utcnow_iso

SESSION_TYPES = {"ADMIN", "TRAINER", "BENEFICIARY"}
DEFAULT_TTL_HOURS = 12


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_optional(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def create_session(engine, subject_type: str, subject_ref: str | int, *, ttl_hours: int = DEFAULT_TTL_HOURS,
                   ip_address: str | None = None, user_agent: str | None = None) -> str:
    subject_type = (subject_type or "").upper().strip()
    if subject_type not in SESSION_TYPES:
        raise ValueError("Type de session non autorisé")
    ttl_hours = max(1, min(int(ttl_hours or DEFAULT_TTL_HOURS), 24 * 30))
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=ttl_hours)
    execute(engine, """INSERT INTO auth_sessions(
        token_hash,subject_type,subject_ref,created_at,last_seen_at,expires_at,revoked_at,ip_hash,user_agent_hash
        ) VALUES(:t,:st,:sr,:c,:ls,:e,NULL,:ip,:ua)""", {
        "t": _hash_token(token), "st": subject_type, "sr": str(subject_ref),
        "c": now.isoformat(), "ls": now.isoformat(), "e": expires.isoformat(),
        "ip": _hash_optional(ip_address), "ua": _hash_optional(user_agent),
    })
    return token


def resolve_session(engine, token: str | None, *, expected_type: str | None = None,
                    touch: bool = True) -> dict[str, Any] | None:
    if not token:
        return None
    row = one(engine, "SELECT * FROM auth_sessions WHERE token_hash=:t", {"t": _hash_token(token)})
    if not row or row.get("revoked_at"):
        return None
    if expected_type and row.get("subject_type") != expected_type.upper():
        return None
    try:
        exp = datetime.fromisoformat(row["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
    except Exception:
        revoke_session(engine, token)
        return None
    if datetime.now(timezone.utc) >= exp:
        revoke_session(engine, token)
        return None
    if touch:
        execute(engine, "UPDATE auth_sessions SET last_seen_at=:n WHERE id=:i", {"n": utcnow_iso(), "i": row["id"]})
        row["last_seen_at"] = utcnow_iso()
    return row


def revoke_session(engine, token: str | None) -> None:
    if not token:
        return
    execute(engine, "UPDATE auth_sessions SET revoked_at=COALESCE(revoked_at,:n) WHERE token_hash=:t", {
        "n": utcnow_iso(), "t": _hash_token(token)
    })


def revoke_subject_sessions(engine, subject_type: str, subject_ref: str | int) -> int:
    rows = q(engine, "SELECT id FROM auth_sessions WHERE subject_type=:st AND subject_ref=:sr AND revoked_at IS NULL", {
        "st": subject_type.upper(), "sr": str(subject_ref)
    })
    if rows:
        execute(engine, "UPDATE auth_sessions SET revoked_at=:n WHERE subject_type=:st AND subject_ref=:sr AND revoked_at IS NULL", {
            "n": utcnow_iso(), "st": subject_type.upper(), "sr": str(subject_ref)
        })
    return len(rows)


def purge_expired_sessions(engine) -> int:
    now = datetime.now(timezone.utc)
    rows = q(engine, "SELECT id,expires_at FROM auth_sessions WHERE revoked_at IS NULL")
    expired = []
    for row in rows:
        try:
            exp = datetime.fromisoformat(row["expires_at"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp <= now:
                expired.append(row["id"])
        except Exception:
            expired.append(row["id"])
    for sid in expired:
        execute(engine, "UPDATE auth_sessions SET revoked_at=:n WHERE id=:i", {"n": utcnow_iso(), "i": sid})
    return len(expired)
