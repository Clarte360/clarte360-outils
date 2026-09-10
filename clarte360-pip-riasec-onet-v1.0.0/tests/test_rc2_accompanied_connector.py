import json
from pathlib import Path

import pytest

from clarte360_pip.connectors.gestion_actions import (
    LaunchTokenError,
    build_launch_token,
    verify_launch_token,
)
from clarte360_pip.domain import RunMode
from clarte360_pip.framework.persistence import build_snapshot
from clarte360_pip.framework.server_store import accompanied_run_path, save_accompanied_snapshot, load_latest_accompanied_snapshot

KEY = "test-only-signing-key-abcdefghijklmnopqrstuvwxyz"


def payload(**overrides):
    base = {
        "v": 1,
        "iat": 1_800_000_000,
        "exp": 1_800_003_600,
        "beneficiary_id": "BEN-1",
        "action_id": "CLA0003",
        "participant_id": "PART-1",
        "prescription_id": "PRESC-1",
        "rights": ["PIP_RUN"],
    }
    base.update(overrides)
    return base


def test_signed_launch_token_resolves_accompanied_context():
    token = build_launch_token(payload(), KEY)
    ctx = verify_launch_token(token, KEY, now_epoch=1_800_000_100)
    assert ctx.mode is RunMode.ACCOMPANIMENT
    assert ctx.beneficiary_id == "BEN-1"
    assert ctx.action_id == "CLA0003"
    assert ctx.prescription_id == "PRESC-1"


def test_tampered_launch_token_is_rejected():
    token = build_launch_token(payload(), KEY)
    p, sig = token.split(".")
    with pytest.raises(LaunchTokenError):
        verify_launch_token(p + "A." + sig, KEY, now_epoch=1_800_000_100)


def test_expired_launch_token_is_rejected():
    token = build_launch_token(payload(exp=1_700_000_000), KEY)
    with pytest.raises(LaunchTokenError):
        verify_launch_token(token, KEY, now_epoch=1_800_000_100)


def test_snapshot_never_exports_scoring_before_pip_completion():
    state = {
        "passation_id": "p1",
        "pip_state": {"completed": False, "answers": {"x": 5}},
        "pip_scoring": {"indices": {"R": 99}},
    }
    snap = build_snapshot(state)
    assert snap["pip_scoring"] == {}


def test_server_store_path_is_scoped_by_action_beneficiary_and_passation(monkeypatch, tmp_path):
    import clarte360_pip.framework.server_store as store
    monkeypatch.setattr(store, "PERSISTENT_DATA_DIR", tmp_path)
    path = accompanied_run_path("CLA0003", "BEN-1", "PASS-9")
    assert path == tmp_path / "accompanied_runs" / "CLA0003" / "BEN-1" / "PASS-9.json"


def test_server_store_rejects_path_traversal(monkeypatch, tmp_path):
    import clarte360_pip.framework.server_store as store
    monkeypatch.setattr(store, "PERSISTENT_DATA_DIR", tmp_path)
    with pytest.raises(ValueError):
        accompanied_run_path("../etc", "BEN-1", "PASS-9")


def test_accompanied_snapshot_can_be_resumed_by_prescription(monkeypatch, tmp_path):
    import clarte360_pip.framework.server_store as store
    monkeypatch.setattr(store, "PERSISTENT_DATA_DIR", tmp_path)
    state = {
        "passation_id": "PASS-9",
        "session_id": "S-1",
        "navigation_page": "pip_questionnaire",
        "journey": "PIP_SEUL",
        "pip_state": {"completed": False, "index": 42, "answers": {"x": 4}},
    }
    save_accompanied_snapshot(state, "CLA0003", "BEN-1", "PRESC-1")
    restored = load_latest_accompanied_snapshot("CLA0003", "BEN-1", "PRESC-1")
    assert restored is not None
    assert restored["passation_id"] == "PASS-9"
    assert restored["pip_state"]["index"] == 42


def test_prescription_pointer_cannot_cross_beneficiary(monkeypatch, tmp_path):
    import clarte360_pip.framework.server_store as store
    monkeypatch.setattr(store, "PERSISTENT_DATA_DIR", tmp_path)
    state = {"passation_id": "PASS-9", "pip_state": {"completed": False}}
    save_accompanied_snapshot(state, "CLA0003", "BEN-1", "PRESC-1")
    with pytest.raises(ValueError):
        load_latest_accompanied_snapshot("CLA0003", "BEN-OTHER", "PRESC-1")
