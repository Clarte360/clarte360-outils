import hashlib
import json
from typing import Any


def canonical_guard_state(*, beneficiaire: Any, cursor_order: Any, positions: Any, rgpd_acceptance: Any, draft_slider: Any = None) -> dict:
    state = {
        "beneficiaire": beneficiaire or {},
        "cursor_order": list(cursor_order or []),
        "positions": {str(k): int(v) for k, v in (positions or {}).items()},
        "rgpd_acceptance": rgpd_acceptance or {},
    }
    if draft_slider is not None:
        state["draft_slider"] = draft_slider
    return state


def fingerprint_guard_state(*, beneficiaire: Any, cursor_order: Any, positions: Any, rgpd_acceptance: Any, draft_slider: Any = None) -> str:
    state = canonical_guard_state(
        beneficiaire=beneficiaire,
        cursor_order=cursor_order,
        positions=positions,
        rgpd_acceptance=rgpd_acceptance,
        draft_slider=draft_slider,
    )
    raw = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
