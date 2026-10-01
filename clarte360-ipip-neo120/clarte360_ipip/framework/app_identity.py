from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import BASE_DIR
from .validation import ValidationError, validate_https_url, validate_safe_id

IDENTITY_FILE = BASE_DIR / "config" / "app_identity.json"


def load_app_identity(path: Path = IDENTITY_FILE) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError("Configuration d'identité applicative invalide.") from exc
    required = ("tool_id", "app_name", "app_version", "production_url", "deployment_status")
    for key in required:
        if not str(payload.get(key, "")).strip():
            raise ValidationError(f"Configuration applicative incomplète : {key}.")
    validate_safe_id(payload["tool_id"], "tool_id")
    validate_https_url(payload["production_url"], "production_url")
    return payload
