"""Offline, descriptive RIASEC context extracted from the supplied ROME PDFs."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


_DATA = Path(__file__).resolve().parents[2] / "resources" / "rome" / "rome_riasec_clarte360_202606.json"


@lru_cache(maxsize=1)
def _mapping() -> dict:
    payload = json.loads(_DATA.read_text(encoding="utf-8"))
    return payload.get("jobs", {}) if isinstance(payload, dict) else {}


def rome_interest_context(rome_code: str) -> dict | None:
    """Return a sourced, non-evaluative RIASEC hint for a ROME job code."""
    code = str(rome_code or "").strip().upper()
    record = _mapping().get(code)
    if record is None:
        return None
    return {
        "rome_code": code,
        "riasec_code": record["riasec_normalized"],
        "source_label": "Corpus de fiches ROME PDF, juin 2026",
    }
