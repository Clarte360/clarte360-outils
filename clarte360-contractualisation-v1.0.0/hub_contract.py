from __future__ import annotations
import hashlib, hmac, json, time
from typing import Any

TOOL_ID='contractualisation'
ALLOWED_ROLES={'admin'}

def canonical_payload(payload: dict[str,Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def verify_hub_context(payload: dict[str,Any], signature: str, secret: str, now: int | None=None) -> dict[str,Any]:
    if not secret:
        raise ValueError('Secret HMAC Hub non configuré.')
    expected=hmac.new(secret.encode(), canonical_payload(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(signature or '')):
        raise ValueError('Signature Hub invalide.')
    if payload.get('tool_id') not in {TOOL_ID,'clarte360-contractualisation'}:
        raise ValueError('tool_id incompatible avec Contractualisation.')
    if payload.get('hub_source') != 'GESTION_ACTIONS_I9':
        raise ValueError('Source Hub non autorisée.')
    role=str(payload.get('role') or '').lower()
    if role not in ALLOWED_ROLES:
        raise ValueError("Contractualisation est réservée au rôle administrateur.")
    exp=payload.get('expires_at')
    if exp is not None and int(exp) < int(now if now is not None else time.time()):
        raise ValueError('Contexte Hub expiré.')
    # The beneficiary is only the dossier subject, never an authenticated user of this tool.
    return payload

def build_status_event(*, action_id: str, prescription_id: str | None, status: str, no_clar: str | None=None) -> dict[str,Any]:
    if status not in {'opened','draft','generated','exported','error'}:
        raise ValueError('Statut Hub non autorisé.')
    return {
        'tool_id': TOOL_ID,
        'action_id': action_id,
        'prescription_id': prescription_id,
        'status': status,
        'no_clar': no_clar,
    }
