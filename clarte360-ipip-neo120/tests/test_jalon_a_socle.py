import json
from pathlib import Path
from clarte360_ipip.framework.config import INTERNAL_PORT, PRODUCTION_URL, SERVICE_NAME, STABLE_PATH, TOOL_ID

def test_identity_reserved_values():
    assert TOOL_ID == "ipip-neo120"
    assert PRODUCTION_URL == "https://ipip-neo120.clarte360.com"
    assert INTERNAL_PORT == 8515
    assert SERVICE_NAME == "clarte360-ipip-neo120.service"
    assert STABLE_PATH == "/opt/clarte360/clarte360-outils/clarte360-ipip-neo120/"

def test_app_identity_matches_config():
    d=json.loads(Path("config/app_identity.json").read_text(encoding="utf-8"))
    assert d["tool_id"] == TOOL_ID
    assert d["internal_port"] == INTERNAL_PORT
    assert d["production_url"] == PRODUCTION_URL
    assert d["service_name"] == SERVICE_NAME
    assert d["deployment_status"] == "reserved_not_deployed"

def test_no_secret_in_identity():
    t=Path("config/app_identity.json").read_text(encoding="utf-8").lower()
    for w in ["password", "api_key", "signing_key", "secret"]: assert w not in t

def test_active_references_present():
    assert Path("resources/ipip/REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json").is_file()
    assert Path("resources/ipip/REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json").is_file()

def test_questionnaire_reference_has_120_items():
    d=json.loads(Path("resources/ipip/REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json").read_text(encoding="utf-8"))
    items=d.get("items") or d.get("questions") or []
    assert len(items) == 120
