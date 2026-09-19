from pathlib import Path

import pytest

from clarte360_pip.connectors.gestion_actions import build_launch_token, verify_launch_token, LaunchTokenError
from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.feeling import QUESTIONS, QUESTIONS_VERSION, build_feeling_record

KEY = "test-only-signing-key-abcdefghijklmnopqrstuvwxyz"

def _payload(**overrides):
    base = {
        "v": 1,
        "iat": 1_800_000_000,
        "exp": 1_800_003_600,
        "beneficiary_id": "BEN-1",
        "action_id": "ACT-TECH-99",
        "participant_id": "PART-1",
        "prescription_id": "PRESC-1",
        "beneficiary_first_name": "Alice",
        "beneficiary_last_name": "Martin",
        "action_number": "CLA0003",
        "action_title": "Bilan de compétences",
        "rights": ["PIP_RUN"],
    }
    base.update(overrides)
    return base

def test_accompaniment_token_carries_signed_display_data_separate_from_ids():
    ctx = verify_launch_token(build_launch_token(_payload(), KEY), KEY, now_epoch=1_800_000_100)
    assert ctx.mode is RunMode.ACCOMPANIMENT
    assert ctx.beneficiary_id == "BEN-1"
    assert ctx.action_id == "ACT-TECH-99"
    assert ctx.beneficiary_display_name == "Alice Martin"
    assert ctx.action_display_label == "CLA0003 — Bilan de compétences"
    assert "BEN-1" not in ctx.beneficiary_display_name
    assert "ACT-TECH-99" not in ctx.action_display_label

def test_legacy_accompaniment_token_without_display_data_stays_accepted_without_exposing_ids():
    data = _payload()
    for key in ("beneficiary_first_name", "beneficiary_last_name", "action_number", "action_title"):
        data.pop(key)
    ctx = verify_launch_token(build_launch_token(data, KEY), KEY, now_epoch=1_800_000_100)
    assert ctx.beneficiary_display_name == "Bénéficiaire Clarté360"
    assert ctx.action_display_label == "Action Clarté360"
    assert ctx.beneficiary_id not in ctx.beneficiary_display_name
    assert ctx.action_id not in ctx.action_display_label

def test_public_context_cannot_carry_dossier_display_data():
    with pytest.raises(ValueError):
        LaunchContext(mode=RunMode.PUBLIC, beneficiary_first_name="Alice").validate()

def test_feeling_has_no_accompaniment_question_and_tracks_mode():
    assert QUESTIONS_VERSION == "PIP-FEELING-1.1"
    assert "dialogue" not in QUESTIONS
    assert "accompagnateur" not in str(QUESTIONS).lower()
    record = build_feeling_record({"global": 4}, "PIP_SEUL", run_mode="ACCOMPAGNEMENT")
    assert record["run_mode"] == "ACCOMPAGNEMENT"

def test_accompanied_home_never_displays_technical_ids():
    src = Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")
    home = src[src.index("def render_home"):src.index("def render_pip_intro")]
    assert "launch.beneficiary_display_name" in home
    assert "launch.action_display_label" in home
    assert 'launch.beneficiary_id}' not in home
    assert 'launch.action_id}' not in home

def test_user_facing_source_contains_no_forbidden_accompaniment_question():
    for relative in ["clarte360_pip/ui/pages.py", "clarte360_pip/feeling.py"]:
        text = Path(relative).read_text(encoding="utf-8").lower()
        assert "souhaitez-vous approfondir certains éléments avec votre accompagnateur" not in text
