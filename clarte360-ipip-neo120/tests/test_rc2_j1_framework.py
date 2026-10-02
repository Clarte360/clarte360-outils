import json
from datetime import datetime, timedelta
from pathlib import Path

from clarte360_ipip.framework.app_identity import load_app_identity
from clarte360_ipip.framework.config import (
    INTERNAL_PORT, LOGO_PATH, PRODUCTION_URL, SERVICE_NAME, STABLE_PATH, TOOL_ID
)
from clarte360_ipip.framework.persistence import SCHEMA, decode_snapshot_bytes, snapshot_bytes
from clarte360_ipip.framework.timeout import is_timed_out
from clarte360_ipip.version import APP_VERSION, FRAMEWORK_VERSION


def test_j1_framework_modules_present():
    expected = [
        "app_identity.py", "branding.py", "config.py", "contact.py", "navigation.py",
        "persistence.py", "rgpd.py", "server_store.py", "session.py", "timeout.py", "validation.py",
    ]
    for name in expected:
        assert (Path("clarte360_ipip/framework") / name).is_file(), name
    for name in ["entry.py", "pages.py", "sidebar.py"]:
        assert (Path("clarte360_ipip/ui") / name).is_file(), name


def test_official_logo_and_icon_are_packaged():
    assert LOGO_PATH.name == "logo_clarte360.png"
    assert LOGO_PATH.is_file() and LOGO_PATH.stat().st_size > 1000
    assert Path("assets/site_icon.png").is_file()


def test_identity_and_version_are_rc2_consistent():
    identity = load_app_identity()
    assert APP_VERSION == "0.8.0-rc2"
    assert identity["app_version"] == APP_VERSION
    assert identity["tool_id"] == TOOL_ID == "ipip-neo120"
    assert identity["production_url"] == PRODUCTION_URL == "https://ipip-neo120.clarte360.com"
    assert identity["internal_port"] == INTERNAL_PORT == 8515
    assert identity["service_name"] == SERVICE_NAME == "clarte360-ipip-neo120.service"
    assert identity["stable_path"] == STABLE_PATH == "/opt/clarte360/clarte360-outils/clarte360-ipip-neo120/"
    assert "V5" in FRAMEWORK_VERSION and "V4.1" in FRAMEWORK_VERSION


def test_sidebar_has_required_j1_entries():
    src = Path("clarte360_ipip/ui/sidebar.py").read_text(encoding="utf-8")
    for label in ["Accueil", "Ma passation / Reprendre", "RGPD et confidentialité", "Mentions / informations", "Contacter Clarté360", "Mode ACCOMPAGNEMENT"]:
        assert label in src


def test_timeout_logic_is_deterministic():
    now = datetime(2026, 10, 1, 20, 0, 0)
    assert not is_timed_out((now - timedelta(minutes=14)).isoformat(), now=now, limit_minutes=15)
    assert is_timed_out((now - timedelta(minutes=16)).isoformat(), now=now, limit_minutes=15)


def test_snapshot_schema_and_validation():
    raw = snapshot_bytes({"run_id":"RUN-1", "answers":{1:1, 2:5}, "block":0, "stage":"questionnaire", "rgpd_acceptance":None})
    decoded = decode_snapshot_bytes(raw)
    assert decoded["schema"] == SCHEMA == "clarte360.ipipneo.run.v1"
    assert decoded["answers"] == {"1":1, "2":5}


def test_app_uses_framework_sidebar_and_timeout_without_public_mode():
    src = Path("app.py").read_text(encoding="utf-8")
    assert "render_sidebar(current_status)" in src
    assert "enforce_timeout()" in src
    assert "mode PUBLIC" not in src
