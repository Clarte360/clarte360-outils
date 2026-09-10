from __future__ import annotations
import json
from pathlib import Path

from clarte360_pip.framework.config import RUNTIME_RESOURCES_DIR

RUNTIME_FILE = RUNTIME_RESOURCES_DIR / "pip_bank_PIP-BANK-0.3.json"


def load_pip_bank(path: Path | None = None) -> dict:
    target = path or RUNTIME_FILE
    with target.open("r", encoding="utf-8") as f:
        return json.load(f)


def item_index(bank: dict) -> dict[str, dict]:
    return {item["item_id"]: item for item in bank["items"]}
