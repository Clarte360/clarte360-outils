from __future__ import annotations
import json
from pathlib import Path

from clarte360_pip.framework.config import RUNTIME_RESOURCES_DIR
from clarte360_pip.version import PIP_BANK_VERSION

RUNTIME_FILE = RUNTIME_RESOURCES_DIR / f"pip_bank_{PIP_BANK_VERSION}.json"


def runtime_file_for_version(bank_version: str) -> Path:
    return RUNTIME_RESOURCES_DIR / f"pip_bank_{bank_version}.json"


def load_pip_bank(path: Path | None = None, bank_version: str | None = None) -> dict:
    target = path or (runtime_file_for_version(bank_version) if bank_version else RUNTIME_FILE)
    if not target.exists():
        raise FileNotFoundError(f"Banque PIP introuvable : {target.name}")
    with target.open("r", encoding="utf-8") as f:
        return json.load(f)


def item_index(bank: dict) -> dict[str, dict]:
    return {item["item_id"]: item for item in bank["items"]}
