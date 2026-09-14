from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
_ALLOWED_EVENTS = {"CONSULTE", "EN_COURS", "TERMINE"}


class PipConnectorError(ValueError):
    pass


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _safe_id(value: Any, field: str) -> str:
    text = str(value or "")
    if not _SAFE_ID.fullmatch(text):
        raise PipConnectorError(f"Identifiant PIP invalide : {field}.")
    return text


def build_pip_launch_token(*, beneficiary_id: Any, action_id: Any, prescription_id: Any,
                           participant_id: Any | None, signing_key: str, rights: list[str] | None = None,
                           valid_seconds: int = 900, now_epoch: int | None = None) -> str:
    """Build the exact compact HMAC-SHA256 contract implemented by PIP RC5."""
    key = (signing_key or "").strip()
    if len(key) < 24:
        raise PipConnectorError("Clé de signature PIP non configurée ou trop courte.")
    now = int(datetime.now(timezone.utc).timestamp()) if now_epoch is None else int(now_epoch)
    ttl = max(60, min(int(valid_seconds), 7 * 24 * 3600))
    payload = {
        "v": 1,
        "iat": now,
        "exp": now + ttl,
        "beneficiary_id": _safe_id(beneficiary_id, "beneficiary_id"),
        "action_id": _safe_id(action_id, "action_id"),
        "prescription_id": _safe_id(prescription_id, "prescription_id"),
        "rights": [str(x) for x in (rights or [])],
    }
    if participant_id is not None:
        payload["participant_id"] = _safe_id(participant_id, "participant_id")
    payload_part = _b64url(_canonical_json(payload))
    signature = hmac.new(key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_part}.{_b64url(signature)}"


def build_pip_launch_url(base_url: str, launch_token: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if not url.startswith("https://") and not url.startswith("http://"):
        raise PipConnectorError("URL PIP non configurée.")
    return f"{url}/?{urlencode({'mode':'accompagnement','launch': launch_token})}"


def event_identity(raw_line: str, source_name: str = "pip_rc5") -> str:
    return f"{source_name}:" + hashlib.sha256(raw_line.encode("utf-8")).hexdigest()


def parse_pip_outbox_line(raw_line: str) -> dict[str, Any]:
    try:
        event = json.loads(raw_line)
    except Exception as exc:
        raise PipConnectorError("Événement PIP illisible.") from exc
    if not isinstance(event, dict) or event.get("event_type") not in _ALLOWED_EVENTS:
        raise PipConnectorError("Type d'événement PIP non autorisé.")
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise PipConnectorError("Charge utile PIP invalide.")
    for field in ("beneficiary_id", "action_id", "prescription_id"):
        _safe_id(payload.get(field), field)
    if payload.get("participant_id") is not None:
        _safe_id(payload.get("participant_id"), "participant_id")
    return event


def read_outbox_from_offset(path: str | Path, offset: int = 0, limit: int = 500) -> tuple[list[tuple[int, str, dict[str, Any]]], int]:
    """Read complete JSONL records only; malformed lines are returned as exceptions to caller."""
    p = Path(path)
    if not p.is_file():
        return [], max(0, int(offset or 0))
    start = max(0, int(offset or 0))
    size = p.stat().st_size
    if start > size:  # rotation/truncation: safely restart, idempotency is DB-enforced.
        start = 0
    rows: list[tuple[int, str, dict[str, Any]]] = []
    next_offset = start
    with p.open("rb") as handle:
        handle.seek(start)
        for _ in range(max(1, int(limit))):
            before = handle.tell()
            raw = handle.readline()
            if not raw:
                break
            after = handle.tell()
            if not raw.endswith(b"\n"):
                # Do not consume a partially-written line.
                next_offset = before
                break
            text = raw.decode("utf-8").rstrip("\r\n")
            if not text.strip():
                next_offset = after
                continue
            rows.append((after, text, parse_pip_outbox_line(text)))
            next_offset = after
    return rows, next_offset
