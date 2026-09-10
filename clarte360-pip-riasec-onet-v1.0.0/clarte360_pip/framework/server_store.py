from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from clarte360_pip.framework.config import PERSISTENT_DATA_DIR
from clarte360_pip.framework.persistence import build_snapshot

_SAFE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")


def _safe(value: str, label: str) -> str:
    if not value or not _SAFE.fullmatch(value):
        raise ValueError(f"{label} invalide pour le stockage serveur.")
    return value


def _atomic_json_write(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".pip-", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def accompanied_run_path(action_id: str, beneficiary_id: str, passation_id: str) -> Path:
    return (
        PERSISTENT_DATA_DIR
        / "accompanied_runs"
        / _safe(action_id, "action_id")
        / _safe(beneficiary_id, "beneficiary_id")
        / f"{_safe(passation_id, 'passation_id')}.json"
    )


def prescription_pointer_path(prescription_id: str) -> Path:
    return PERSISTENT_DATA_DIR / "accompanied_runs" / "_prescriptions" / f"{_safe(prescription_id, 'prescription_id')}.json"


def save_accompanied_snapshot(
    session_state: dict[str, Any],
    action_id: str,
    beneficiary_id: str,
    prescription_id: str | None = None,
) -> Path:
    passation_id = str(session_state.get("passation_id") or "")
    target = accompanied_run_path(action_id, beneficiary_id, passation_id)
    payload = build_snapshot(session_state)
    _atomic_json_write(target, payload)
    if prescription_id:
        pointer = {
            "action_id": _safe(action_id, "action_id"),
            "beneficiary_id": _safe(beneficiary_id, "beneficiary_id"),
            "prescription_id": _safe(prescription_id, "prescription_id"),
            "passation_id": _safe(passation_id, "passation_id"),
        }
        _atomic_json_write(prescription_pointer_path(prescription_id), pointer)
    return target


def load_accompanied_snapshot(action_id: str, beneficiary_id: str, passation_id: str) -> dict[str, Any]:
    path = accompanied_run_path(action_id, beneficiary_id, passation_id)
    return json.loads(path.read_text(encoding="utf-8"))


def load_latest_accompanied_snapshot(action_id: str, beneficiary_id: str, prescription_id: str) -> dict[str, Any] | None:
    pointer_path = prescription_pointer_path(prescription_id)
    if not pointer_path.exists():
        return None
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("action_id") != action_id or pointer.get("beneficiary_id") != beneficiary_id:
        raise ValueError("La sauvegarde liée à cette prescription ne correspond pas au bénéficiaire/action.")
    return load_accompanied_snapshot(action_id, beneficiary_id, str(pointer.get("passation_id") or ""))
