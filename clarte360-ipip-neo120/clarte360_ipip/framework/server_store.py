from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from typing import Any
from .validation import validate_safe_id


def atomic_json_write(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".ipip-", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def safe_run_path(base_dir: Path, category: str, run_id: str, suffix: str = ".json") -> Path:
    safe = validate_safe_id(run_id, "run_id")
    return base_dir / category / f"{safe}{suffix}"
