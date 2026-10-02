from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from clarte360_ipip.version import APP_VERSION, FRAMEWORK_REFERENCE, FRAMEWORK_VERSION, FRAMEWORK_VPS_VERSION

BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"
RESOURCES_DIR = BASE_DIR / "resources"
PERSISTENT_DATA_DIR = Path(os.getenv("CLARTE360_IPIP_DATA_DIR", "/var/lib/clarte360/ipip-neo120")).expanduser()
REPORTS_DIR = PERSISTENT_DATA_DIR / "reports"
TEMP_DIR = Path(os.getenv("CLARTE360_IPIP_TEMP_DIR", "/tmp/clarte360-ipip-neo120")).expanduser()
SITE_ICON_PATH = ASSETS_DIR / "site_icon.png"
LOGO_PATH = ASSETS_DIR / "logo_clarte360.png"

APP_NAME = "Clarté360 - Profil de fonctionnement professionnel"
APP_SHORT_NAME = "Profil de fonctionnement professionnel"
TOOL_ID = "ipip-neo120"
PRODUCTION_URL = "https://ipip-neo120.clarte360.com"
INTERNAL_PORT = 8515
SERVICE_NAME = "clarte360-ipip-neo120.service"
STABLE_PATH = "/opt/clarte360/clarte360-outils/clarte360-ipip-neo120/"

OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
DEFAULT_SESSION_LIMIT_MINUTES = 15
RGPD_TEXT_VERSION = "RGPD-Clarte360-IPIP-v1.6-J2-20261001"

CLARTE360_LEGAL = {
    "raison_sociale": "Clarté360",
    "forme": "SAS",
    "adresse": "60 rue François 1er",
    "code_postal_ville": "75008 Paris",
    "telephone": "01 89 48 08 25",
    "email": "contact@clarte360.com",
    "web": "www.clarte360.com",
    "rcs": "102349834",
    "siret": "10234983400014",
    "naf": "8559 A",
    "tva": "FR88102349834",
}


@dataclass(frozen=True)
class GestionActionsSettings:
    launch_signing_key: str | None

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


def load_gestion_actions_settings(secrets: Mapping[str, Any] | None = None) -> GestionActionsSettings:
    section = _section(secrets, "IPIP_CONNECTOR")
    key = str(section.get("LAUNCH_SIGNING_KEY", "")).strip() or None
    return GestionActionsSettings(key)


def ensure_runtime_directories() -> None:
    PERSISTENT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def public_runtime_metadata() -> dict[str, str]:
    return {
        "app_version": APP_VERSION,
        "framework_reference": FRAMEWORK_REFERENCE,
        "framework_version": FRAMEWORK_VERSION,
        "framework_vps_version": FRAMEWORK_VPS_VERSION,
    }
