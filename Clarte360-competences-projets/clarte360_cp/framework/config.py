from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"
DEFAULT_DATA_DIR = Path("/var/lib/clarte360/competences-projets")
DATA_DIR = Path(os.getenv("CLARTE360_CP_DATA_DIR", str(DEFAULT_DATA_DIR))).expanduser()
DB_DIR = DATA_DIR / "db"
OBJECTS_DIR = DATA_DIR / "objects" / "sha256"
OUTBOX_DIR = DATA_DIR / "outbox"
RECEIPTS_DIR = DATA_DIR / "receipts"
RUNTIME_CACHE_DIR = DATA_DIR / "runtime-cache"
QUARANTINE_DIR = DATA_DIR / "quarantine"
TEMP_DIR = Path(os.getenv("CLARTE360_CP_TEMP_DIR", "/tmp/clarte360-competences-projets")).expanduser()
DATABASE_URL = os.getenv("CLARTE360_CP_DATABASE_URL", f"sqlite:///{DB_DIR / 'competences_projets.sqlite3'}")
LOGO_PATH = ASSETS_DIR / "site_icon.png"

APP_SHORT_NAME = "Clarté360 - Compétences & Projets"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
DEFAULT_SESSION_LIMIT_MINUTES = 60
BACKUP_RETENTION_DAYS = 30
TECHNICAL_LOG_RETENTION_DAYS = 365
FOLLOWUP_MAX_RETENTION_YEARS = 3


@dataclass(frozen=True)
class ConnectorSettings:
    launch_signing_key: str | None
    outbox_pending_dir: str | None

    @property
    def configured(self) -> bool:
        return bool(self.launch_signing_key and self.launch_signing_key.strip())


def _section(secrets: Mapping[str, Any] | None, key: str) -> Mapping[str, Any]:
    if not secrets:
        return {}
    try:
        value = secrets.get(key, {})
    except Exception:
        return {}
    return value if isinstance(value, Mapping) else {}


def load_connector_settings(secrets: Mapping[str, Any] | None = None) -> ConnectorSettings:
    section = _section(secrets, "COMPETENCES_PROJETS_CONNECTOR")
    key = str(section.get("LAUNCH_SIGNING_KEY", "")).strip() or None
    outbox = str(section.get("OUTBOX_PENDING_DIR", "")).strip() or None
    return ConnectorSettings(key, outbox)


def session_limit_minutes(secrets: Mapping[str, Any] | None = None) -> int:
    section = _section(secrets, "security")
    try:
        value = int(section.get("session_timeout_minutes", DEFAULT_SESSION_LIMIT_MINUTES))
    except (TypeError, ValueError):
        return DEFAULT_SESSION_LIMIT_MINUTES
    # A one-hour working window is the minimum so a long interview or writing
    # break cannot destroy the active browser session. Explicitly bounded at
    # four hours for shared-screen and public-terminal safety.
    return max(60, min(value, 240))


def ensure_runtime_directories() -> None:
    for path in (DB_DIR, OBJECTS_DIR, OUTBOX_DIR, RECEIPTS_DIR, RUNTIME_CACHE_DIR, QUARANTINE_DIR, TEMP_DIR):
        path.mkdir(parents=True, exist_ok=True)
