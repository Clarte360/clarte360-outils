from __future__ import annotations

import json
from pathlib import Path

from clarte360_cp.framework.app_identity import load_app_identity

ROOT = Path(__file__).resolve().parents[1]


def test_go16_identity_exact():
    identity = load_app_identity()
    assert identity["tool_id"] == "competences-projets"
    assert identity["tool_code"] == "COMPETENCES_PROJETS"
    assert identity["target_url"] == "https://competences-projets.clarte360.com"
    assert identity["internal_port"] == 8514
    assert identity["service"] == "clarte360-competences-projets.service"
    assert identity["stable_path"] == "/opt/clarte360/clarte360-outils/clarte360-competences-projets/"
    assert identity["data_path"] == "/var/lib/clarte360/competences-projets/"
    assert identity["deployment_status"] == "candidate"
    assert identity["mode"] == "ACCOMPAGNEMENT"


def test_modular_structure_exists():
    required = [
        "clarte360_cp/framework", "clarte360_cp/domain", "clarte360_cp/application",
        "clarte360_cp/repositories", "clarte360_cp/connectors", "clarte360_cp/ui",
        "clarte360_cp/reporting", "config", "resources", "tests", "migrations", "deploy",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel


def test_no_pip_business_modules_reused():
    forbidden = ["scoring.py", "questionnaire", "onet.py", "pip_data"]
    all_paths = {str(p.relative_to(ROOT)) for p in ROOT.rglob("*")}
    for needle in forbidden:
        assert not any(needle in p for p in all_paths), needle


def test_secrets_example_has_no_real_secret():
    text = (ROOT / ".streamlit" / "secrets.example.toml").read_text(encoding="utf-8")
    assert 'LAUNCH_SIGNING_KEY = ""' in text
    assert 'OUTBOX_PENDING_DIR = ""' in text
    assert "sk-" not in text.lower()


def test_requirements_reproducible_minimal():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "streamlit" in req and "SQLAlchemy" in req and "pytest" in req
    assert "onet" not in req.lower()
