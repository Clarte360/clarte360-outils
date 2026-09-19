import json
from pathlib import Path

from clarte360_pip.framework.persistence import build_snapshot, restore_snapshot
from clarte360_pip.framework.public_access import save_public_study_record, STUDY_SCHEMA


def _public_completed_state():
    return {
        "passation_id": "PASS-PUBLIC-H31",
        "session_id": "SESSION-H31",
        "navigation_page": "finished",
        "last_useful_page": "finished",
        "public_participant_id": "INTERNAL-CRM-ONLY",
        "public_identity": {"first_name": "Test", "last_name": "Public", "email": "test@example.org", "phone": "0600000000"},
        "public_access_verified": True,
        "study_consent": True,
        "journey": "PIP_SEUL",
        "pip_state": {
            "bank_version": "PIP-BANK-0.5",
            "order": [f"Q{i:02d}" for i in range(72)],
            "answers": {f"Q{i:02d}": ((i % 5) + 1) for i in range(72)},
            "index": 71,
            "completed": True,
        },
        "pip_scoring": {"algorithm_version": "PIP-SCORE-0.5", "indices": {"R": 50, "I": 55, "A": 60, "S": 65, "E": 70, "C": 45}},
        "onet_state": {},
        "feeling": {"answers": {"global": 4}},
        "session_history": [],
    }


def test_h31_snapshot_persists_and_restores_public_study_id(monkeypatch, tmp_path):
    import clarte360_pip.framework.public_access as pa
    monkeypatch.setattr(pa, "STUDY_DIR", tmp_path / "study")
    state = _public_completed_state()
    first_path = save_public_study_record(state)
    first_id = state["public_study_id"]
    assert first_path and first_path.name == first_id + ".json"

    snap = build_snapshot(state)
    assert snap["public_study_id"] == first_id
    assert len(snap["pip_state"]["answers"]) == 72

    restored = {}
    restore_snapshot(snap, restored)
    assert restored["navigation_page"] == "finished"
    assert len(restored["pip_state"]["answers"]) == 72
    assert restored["public_study_id"] == first_id

    second_path = save_public_study_record(restored)
    assert restored["public_study_id"] == first_id
    assert second_path == first_path
    assert len(list((tmp_path / "study").glob("*.json"))) == 1
    payload = json.loads(second_path.read_text(encoding="utf-8"))
    assert payload["schema"] == STUDY_SCHEMA
    assert payload["study_id"] == first_id


def test_h31_same_json_reloaded_twice_keeps_one_logical_study(monkeypatch, tmp_path):
    import clarte360_pip.framework.public_access as pa
    monkeypatch.setattr(pa, "STUDY_DIR", tmp_path / "study")
    original = _public_completed_state()
    save_public_study_record(original)
    raw_json = json.loads(json.dumps(build_snapshot(original)))

    a, b = {}, {}
    restore_snapshot(raw_json, a)
    save_public_study_record(a)
    restore_snapshot(raw_json, b)
    save_public_study_record(b)

    assert a["public_study_id"] == b["public_study_id"] == raw_json["public_study_id"]
    assert len(list((tmp_path / "study").glob("*.json"))) == 1


def test_h31_study_id_never_leaks_to_crm_snapshot_identity_fields():
    state = _public_completed_state()
    state["public_study_id"] = "STUDY-SECRET-ONLY"
    snap = build_snapshot(state)
    # Snapshot may retain study_id for resume; CRM identity remains logically separate.
    assert snap["public_study_id"] == "STUDY-SECRET-ONLY"
    assert "public_study_id" not in snap["public_identity"]
    assert "study_id" not in snap["public_identity"]
