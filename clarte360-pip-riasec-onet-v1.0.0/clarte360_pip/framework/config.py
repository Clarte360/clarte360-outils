from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from clarte360_pip.version import APP_VERSION, FRAMEWORK_VERSION, FRAMEWORK_VPS_VERSION

BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"
RESOURCES_DIR = BASE_DIR / "resources"
RUNTIME_RESOURCES_DIR = RESOURCES_DIR / "runtime"
SCHEMAS_DIR = RESOURCES_DIR / "schemas"

# Donnees d'execution: volontairement separees des ressources versionnees.
# Le dossier par defaut est ignore par Git. Sur VPS il peut etre externalise
# sans modifier le code via CLARTE360_PIP_DATA_DIR.
PERSISTENT_DATA_DIR = Path(
    os.getenv("CLARTE360_PIP_DATA_DIR", str(BASE_DIR / "data"))
).expanduser()
REPORTS_DIR = PERSISTENT_DATA_DIR / "reports"
TEMP_DIR = Path(
    os.getenv("CLARTE360_PIP_TEMP_DIR", "/tmp/clarte360-pip-riasec-onet")
).expanduser()
LOGO_PATH = ASSETS_DIR / "site_icon.png"

APP_NAME = "PIP RIASEC Clarte360 + O*NET Interest Profiler"
APP_SHORT_NAME = "PIP RIASEC Clarte360"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
RGPD_TEXT_VERSION = "RGPD-Clarte360-PIP-v0.1-2026-09"
DEFAULT_SESSION_LIMIT_MINUTES = 15

CLARTE360_LEGAL = {
    "raison_sociale": "Clarte360",
    "forme": "SAS",
    "adresse": "60 rue Francois 1er",
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
class OnetSettings:
    api_key: str | None
    base_url: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())


@dataclass(frozen=True)
class GestionActionsSettings:
    launch_signing_key: str | None

    @property
    def configured(self) -> bool:
        return bool(self.launch_signing_key and self.launch_signing_key.strip())


@dataclass(frozen=True)
class SmtpSettings:
    server: str | None
    port: int
    username: str | None
    password: str | None
    from_email: str | None
    to_email: str | None

    @property
    def configured(self) -> bool:
        return bool(self.server and self.username and self.password and self.from_email)


def _section(secrets: Mapping[str, Any] | None, key: str) -> Mapping[str, Any]:
    if not secrets:
        return {}
    try:
        value = secrets.get(key, {})
    except Exception:
        return {}
    return value if isinstance(value, Mapping) else {}


def load_onet_settings(secrets: Mapping[str, Any] | None = None) -> OnetSettings:
    section = _section(secrets, "ONET")
    key = str(section.get("ONET_API_KEY", "")).strip() or None
    base = str(section.get("ONET_API_BASE_URL", "https://api-v2.onetcenter.org")).strip()
    return OnetSettings(api_key=key, base_url=base or "https://api-v2.onetcenter.org")


def load_gestion_actions_settings(secrets: Mapping[str, Any] | None = None) -> GestionActionsSettings:
    section = _section(secrets, "PIP_CONNECTOR")
    key = str(section.get("LAUNCH_SIGNING_KEY", "")).strip() or None
    return GestionActionsSettings(launch_signing_key=key)


def load_smtp_settings(secrets: Mapping[str, Any] | None = None) -> SmtpSettings:
    section = _section(secrets, "email")
    return SmtpSettings(
        server=str(section.get("smtp_server", "")).strip() or None,
        port=int(section.get("smtp_port", 465) or 465),
        username=str(section.get("smtp_user", "")).strip() or None,
        password=str(section.get("smtp_password", "")).strip() or None,
        from_email=str(section.get("from_email", "")).strip() or None,
        to_email=str(section.get("to_email", "")).strip() or None,
    )


def ensure_runtime_directories() -> None:
    """Cree uniquement les repertoires locaux d'execution, jamais les ressources Git."""
    PERSISTENT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def public_runtime_metadata() -> dict[str, str]:
    return {
        "app_version": APP_VERSION,
        "framework_version": FRAMEWORK_VERSION,
        "framework_vps_version": FRAMEWORK_VPS_VERSION,
    }
