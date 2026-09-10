import json
from dataclasses import asdict

from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.framework.persistence import build_snapshot, snapshot_bytes, validate_snapshot


def state():
    return {
        "passation_id": "PIP-1",
        "session_id": "S1",
        "launch_context": LaunchContext(mode=RunMode.PUBLIC),
        "rgpd_acceptance": None,
        "navigation_page": "accueil",
        "pip_state": {},
        "session_history": [],
    }


def test_snapshot_is_json_and_framework_business_separated():
    payload = build_snapshot(state())
    assert payload["schema"] == "clarte360.pip.run.v1"
    assert payload["launch_context"]["mode"] == "PUBLIC"
    assert payload["pip_state"] == {}
    assert validate_snapshot(payload) == []
    assert json.loads(snapshot_bytes(state()).decode("utf-8"))["passation_id"] == "PIP-1"
