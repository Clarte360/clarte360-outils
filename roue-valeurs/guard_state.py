import hashlib
import json
from copy import deepcopy


def business_state_payload(data: dict) -> dict:
    """Return the stable business subset used by the unsaved-work guard."""
    if not isinstance(data, dict):
        return {}
    return {
        "beneficiaire": deepcopy(data.get("beneficiaire", {})),
        "progression": deepcopy(data.get("progression", {})),
        "valeurs": deepcopy(data.get("valeurs", [])),
        "valeurs_energies": deepcopy(data.get("valeurs_energies", {})),
    }


def business_state_fingerprint(data: dict) -> str:
    raw = json.dumps(
        business_state_payload(data),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
