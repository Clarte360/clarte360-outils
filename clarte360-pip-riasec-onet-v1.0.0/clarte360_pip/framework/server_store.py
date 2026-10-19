from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any
from clarte360_pip.framework.config import PERSISTENT_DATA_DIR
from clarte360_pip.framework.persistence import build_snapshot, validate_snapshot
from clarte360_pip.framework.storage_io import atomic_json, storage_lock

_SAFE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")


class SnapshotConflict(ValueError):
    """Refuse a stale session rather than replacing an existing passation."""


def _safe(value: str, label: str) -> str:
    if not isinstance(value, str) or value in {'', '.', '..'} or not _SAFE.fullmatch(value):
        raise ValueError(f"{label} invalide pour le stockage serveur.")
    return value


def _atomic_json_write(target: Path, payload: dict[str, Any]) -> None:
    atomic_json(target, payload)


def accompanied_run_path(action_id: str, beneficiary_id: str, passation_id: str) -> Path:
    return (PERSISTENT_DATA_DIR / 'accompanied_runs' / _safe(action_id, 'action_id')
            / _safe(beneficiary_id, 'beneficiary_id') / f"{_safe(passation_id, 'passation_id')}.json")


def prescription_pointer_path(prescription_id: str) -> Path:
    return PERSISTENT_DATA_DIR / 'accompanied_runs' / '_prescriptions' / f"{_safe(prescription_id, 'prescription_id')}.json"


def _pointer(action_id: str, beneficiary_id: str, prescription_id: str) -> dict | None:
    path = prescription_pointer_path(prescription_id)
    if not path.exists():
        return None
    pointer = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(pointer, dict) or any(pointer.get(k) != v for k, v in (
            ('action_id', action_id), ('beneficiary_id', beneficiary_id), ('prescription_id', prescription_id))):
        raise SnapshotConflict("Le rattachement de la prescription est incoherent.")
    _safe(pointer.get('passation_id'), 'passation_id')
    return pointer


def _assert_context(payload: dict, action_id: str, beneficiary_id: str, prescription_id: str) -> None:
    context = payload.get('launch_context')
    if context is None:  # legacy snapshots rely on the scoped server pointer
        return
    if not isinstance(context, dict) or any(context.get(k) != v for k, v in (
            ('mode', 'ACCOMPAGNEMENT'), ('action_id', action_id),
            ('beneficiary_id', beneficiary_id), ('prescription_id', prescription_id))):
        raise SnapshotConflict("La sauvegarde ne correspond pas a cette prescription.")


def save_accompanied_snapshot(session_state: dict[str, Any], action_id: str,
                              beneficiary_id: str, prescription_id: str | None = None) -> Path:
    if session_state.get('server_resume_error'):
        raise SnapshotConflict("La reprise doit reussir avant une nouvelle sauvegarde.")
    passation_id = str(session_state.get('passation_id') or '')
    target = accompanied_run_path(action_id, beneficiary_id, passation_id)
    payload = build_snapshot(session_state)
    if validate_snapshot(payload):
        raise SnapshotConflict("La sauvegarde est invalide ; l'ancienne version est conservee.")
    lock_id = _safe(prescription_id or passation_id, 'prescription_id')
    with storage_lock(PERSISTENT_DATA_DIR / '.locks' / f'accompanied-{lock_id}.lock'):
        if prescription_id:
            _assert_context(payload, action_id, beneficiary_id, prescription_id)
            pointer = _pointer(action_id, beneficiary_id, prescription_id)
            if pointer and pointer['passation_id'] != passation_id:
                raise SnapshotConflict("Une autre session est deja rattachee a cette prescription.")
        if target.exists():
            previous = json.loads(target.read_text(encoding='utf-8'))
            for instrument in ('pip_state', 'onet_state'):
                old = previous.get(instrument) or {}
                new = payload.get(instrument) or {}
                if len(new.get('answers') or {}) < len(old.get('answers') or {}):
                    raise SnapshotConflict("Une session plus avancee existe. Reprenez-la depuis votre espace.")
            if previous.get('completed_at') and not payload.get('completed_at'):
                raise SnapshotConflict("Cette passation a deja ete finalisee.")
        _atomic_json_write(target, payload)
        if prescription_id:
            _atomic_json_write(prescription_pointer_path(prescription_id), {
                'action_id': _safe(action_id, 'action_id'),
                'beneficiary_id': _safe(beneficiary_id, 'beneficiary_id'),
                'prescription_id': _safe(prescription_id, 'prescription_id'),
                'passation_id': _safe(passation_id, 'passation_id'),
            })
    return target


def load_accompanied_snapshot(action_id: str, beneficiary_id: str, passation_id: str) -> dict[str, Any]:
    path = accompanied_run_path(action_id, beneficiary_id, passation_id)
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict) or payload.get('passation_id') != passation_id:
        raise SnapshotConflict("Identifiant de sauvegarde incoherent.")
    return payload


def load_latest_accompanied_snapshot(action_id: str, beneficiary_id: str, prescription_id: str) -> dict[str, Any] | None:
    pointer = _pointer(action_id, beneficiary_id, prescription_id)
    if pointer is None:
        return None
    payload = load_accompanied_snapshot(action_id, beneficiary_id, pointer['passation_id'])
    _assert_context(payload, action_id, beneficiary_id, prescription_id)
    return payload
