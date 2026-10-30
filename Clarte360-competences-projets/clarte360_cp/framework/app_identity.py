from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .validation import ValidationError, validate_https_url, validate_safe_id

BASE_DIR = Path(__file__).resolve().parents[2]
IDENTITY_FILE = BASE_DIR / "config" / "app_identity.json"

REQUIRED = (
    "tool_id", "tool_code", "app_name", "app_version", "target_url", "internal_port",
    "service", "stable_path", "data_path", "deployment_status", "mode", "scope_vocab",
)


def load_app_identity(path: Path = IDENTITY_FILE) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError("Configuration d'identité applicative invalide.") from exc
    for key in REQUIRED:
        if payload.get(key) in (None, ""):
            raise ValidationError(f"Configuration applicative incomplète : {key}.")
    validate_safe_id(payload["tool_id"], "tool_id")
    validate_safe_id(payload["tool_code"], "tool_code")
    validate_https_url(payload["target_url"], "target_url")
    if int(payload["internal_port"]) != 8514:
        raise ValidationError("Port interne incohérent avec GO-16.")
    if payload["mode"] != "ACCOMPAGNEMENT" or payload["scope_vocab"] != "CP_V1":
        raise ValidationError("Mode ou vocabulaire de scopes incohérent.")
    return payload
