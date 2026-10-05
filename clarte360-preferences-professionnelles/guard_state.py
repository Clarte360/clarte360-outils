"""Etat de sauvegarde pour le garde-fou navigateur Clarte360.

Le fingerprint ne contient que des donnees metier susceptibles d'etre perdues.
Les timestamps, traces de session et metadonnees techniques sont volontairement exclus.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def _stable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _stable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_stable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def business_state_payload(state: Mapping[str, Any]) -> dict[str, Any]:
    pending_widgets = {
        str(k): v
        for k, v in state.items()
        if str(k).startswith("radio_Q") and v not in (None, "")
    }
    return {
        "beneficiaire": state.get("beneficiaire", {}),
        "answers": state.get("answers", {}),
        "current_index": state.get("current_index", 0),
        "question_order": state.get("question_order", []),
        "option_orders": state.get("option_orders", {}),
        "pending_widgets": pending_widgets,
    }


def persisted_business_state_payload(state: Mapping[str, Any]) -> dict[str, Any]:
    """Etat réellement sérialisé dans le JSON de reprise.

    Les widgets de réponse non encore validés n'en font pas partie : ils doivent
    donc continuer à déclencher le garde-fou même après téléchargement d'un JSON.
    """
    return {
        "beneficiaire": state.get("beneficiaire", {}),
        "answers": state.get("answers", {}),
        "current_index": state.get("current_index", 0),
        "question_order": state.get("question_order", []),
        "option_orders": state.get("option_orders", {}),
        "pending_widgets": {},
    }


def _fingerprint_payload(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(_stable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint(state: Mapping[str, Any]) -> str:
    return _fingerprint_payload(business_state_payload(state))


def persisted_fingerprint(state: Mapping[str, Any]) -> str:
    """Empreinte de l'état couvert par le JSON effectivement rendu."""
    return _fingerprint_payload(persisted_business_state_payload(state))


def is_dirty(state: Mapping[str, Any], saved_fingerprint: str | None) -> bool:
    if not state.get("test_started"):
        return False
    if not saved_fingerprint:
        return True
    return fingerprint(state) != saved_fingerprint
