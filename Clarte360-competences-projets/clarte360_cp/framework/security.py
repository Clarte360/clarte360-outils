from __future__ import annotations

import re
from typing import Any

FORBIDDEN_LOG_KEYS = {
    "cv", "cv_raw", "document_content", "prompt", "prompt_system", "token", "bearer",
    "launch_token", "signing_key", "secret", "password", "email", "phone",
}
_SECRETISH = re.compile(r"(bearer\s+[A-Za-z0-9._-]+|-----BEGIN .*PRIVATE KEY-----)", re.I)


def minimize_log_fields(fields: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in fields.items():
        if key.lower() in FORBIDDEN_LOG_KEYS:
            continue
        text = str(value)
        if _SECRETISH.search(text):
            safe[key] = "[REDACTED]"
        elif len(text) > 500:
            safe[key] = text[:500] + "…"
        else:
            safe[key] = value
    return safe
