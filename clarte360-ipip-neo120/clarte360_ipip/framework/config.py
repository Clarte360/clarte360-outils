from __future__ import annotations
import os
from pathlib import Path
from clarte360_ipip.version import APP_VERSION, FRAMEWORK_REFERENCE, FRAMEWORK_VERSION, FRAMEWORK_VPS_VERSION
BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"
RESOURCES_DIR = BASE_DIR / "resources"
PERSISTENT_DATA_DIR = Path(os.getenv("CLARTE360_IPIP_DATA_DIR", "/var/lib/clarte360/ipip-neo120")).expanduser()
TEMP_DIR = Path(os.getenv("CLARTE360_IPIP_TEMP_DIR", "/tmp/clarte360-ipip-neo120")).expanduser()
LOGO_PATH = ASSETS_DIR / "site_icon.png"
APP_NAME = "Clarte360 - Profil de fonctionnement professionnel"
APP_SHORT_NAME = "Profil de fonctionnement Clarte360"
TOOL_ID = "ipip-neo120"
PRODUCTION_URL = "https://ipip-neo120.clarte360.com"
INTERNAL_PORT = 8515
SERVICE_NAME = "clarte360-ipip-neo120.service"
STABLE_PATH = "/opt/clarte360/clarte360-outils/clarte360-ipip-neo120/"

def public_runtime_metadata():
    return {"app_version": APP_VERSION, "framework_reference": FRAMEWORK_REFERENCE, "framework_version": FRAMEWORK_VERSION, "framework_vps_version": FRAMEWORK_VPS_VERSION}

from dataclasses import dataclass
from typing import Any, Mapping
@dataclass(frozen=True)
class GestionActionsSettings:
    launch_signing_key: str | None
    @property
    def configured(self): return bool(self.launch_signing_key and self.launch_signing_key.strip())
def load_gestion_actions_settings(secrets: Mapping[str,Any]|None=None)->GestionActionsSettings:
    try: section=(secrets or {}).get('IPIP_CONNECTOR',{})
    except Exception: section={}
    key=str(section.get('LAUNCH_SIGNING_KEY','')).strip() or None if isinstance(section,Mapping) else None
    return GestionActionsSettings(key)
