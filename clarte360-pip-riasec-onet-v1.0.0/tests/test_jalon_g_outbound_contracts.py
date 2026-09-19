import json
from pathlib import Path

import pytest

from clarte360_pip.connectors.gestion_actions import GestionActionsPort, persist_report_document
from clarte360_pip.framework.public_access import save_public_study_record


def test_outbox_is_idempotent_and_retryable(monkeypatch, tmp_path):
    import clarte360_pip.connectors.gestion_actions as ga
    monkeypatch.setattr(ga, "PERSISTENT_DATA_DIR", tmp_path)
    port = GestionActionsPort(None)
    payload = {"source": "PIP_PUBLIC", "email": "a@example.org"}
    p1 = port.publish_event("CONTACT_EMAIL_VERIFIED", payload)
    p2 = port.publish_event("CONTACT_EMAIL_VERIFIED", payload)
    assert p1 == p2
    assert len(port.pending_events()) == 1

    def failing_sender(_):
        raise RuntimeError("hub unavailable")

    result = port.retry_pending(failing_sender)
    assert result == {"delivered": 0, "failed": 1}
    event = json.loads(p1.read_text(encoding="utf-8"))
    assert event["status"] == "PENDING"
    assert event["attempts"] == 1
    assert "hub unavailable" in event["last_error"]

    delivered = []
    result = port.retry_pending(lambda event: delivered.append(event["event_id"]))
    assert result == {"delivered": 1, "failed": 0}
    assert len(delivered) == 1
    assert not p1.exists()
    delivered_files = list((tmp_path / "connector_outbox" / "gestion_actions" / "delivered").glob("*.json"))
    assert len(delivered_files) == 1


def test_public_contract_event_types_are_allowed(monkeypatch, tmp_path):
    import clarte360_pip.connectors.gestion_actions as ga
    monkeypatch.setattr(ga, "PERSISTENT_DATA_DIR", tmp_path)
    port = GestionActionsPort(None)
    for typ in ("CONTACT_EMAIL_VERIFIED", "CONTACT_UPDATED", "CALLBACK_REQUESTED"):
        path = port.publish_event(typ, {"source": "PIP_PUBLIC", "email": "a@example.org", "marker": typ})
        assert path.exists()


def test_callback_payload_never_contains_results_by_contract_source():
    src = Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")
    block = src[src.index('callback_payload = {'):src.index('GestionActionsPort(None).publish_event("CALLBACK_REQUESTED"')]
    forbidden = ("pip_scoring", "holland_code", "scores", "indices", "onet_state", "answers")
    assert all(word not in block for word in forbidden)
    assert "email" in block and "phone" in block and "requested_at" in block


def test_termine_is_only_published_after_pdf_generation_and_feeling():
    src = Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")
    assert '_publish_if_accompanied("TERMINE")' not in src
    finished = src[src.index("def render_finished"):src.index("def _onet_port")]
    assert "build_pip_report_pdf" in finished
    assert 'publish_event("TERMINE"' in finished
    assert finished.index("build_pip_report_pdf") < finished.index('publish_event("TERMINE"')
    final_payload = src[src.index("def _accompanied_final_payload"):src.index("def _save_if_accompanied")]
    assert '"feeling"' in final_payload
    assert '"documents"' in final_payload
    assert '"scores"' in final_payload
    assert "answers" not in final_payload


def test_report_document_reference_contains_integrity_metadata(monkeypatch, tmp_path):
    import clarte360_pip.connectors.gestion_actions as ga
    monkeypatch.setattr(ga, "PERSISTENT_DATA_DIR", tmp_path)
    ref = persist_report_document("PASS-1", "report.pdf", b"%PDF-test")
    assert ref["file_name"] == "report.pdf"
    assert ref["mime_type"] == "application/pdf"
    assert ref["size_bytes"] == 9
    assert len(ref["sha256"]) == 64
    assert (tmp_path / ref["storage_ref"]).exists()


def test_public_study_dataset_has_no_crm_join_key(monkeypatch, tmp_path):
    import clarte360_pip.framework.public_access as pa
    monkeypatch.setattr(pa, "STUDY_DIR", tmp_path / "study")
    state = {
        "public_participant_id": "PUB-CRM-123",
        "passation_id": "PASS-CRM-123",
        "public_identity": {"email": "person@example.org"},
        "study_consent": True,
        "journey": "PIP_SEUL",
        "pip_state": {"bank_version": "PIP-BANK-0.5", "answers": {"Q1": 3}},
        "pip_scoring": {"indices": {"R": 50}},
        "onet_state": {},
        "feeling": {},
    }
    path = save_public_study_record(state)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = json.dumps(payload)
    assert payload["schema"] == "clarte360.pip.public-study.v1"
    assert "public_participant_id" not in payload
    assert "passation_id" not in payload
    assert "public_identity" not in payload
    assert "PUB-CRM-123" not in raw
    assert "PASS-CRM-123" not in raw
    assert "person@example.org" not in raw
    assert len(payload["study_id"]) == 32


def test_study_ids_are_independent_across_fresh_sessions(monkeypatch, tmp_path):
    import clarte360_pip.framework.public_access as pa
    monkeypatch.setattr(pa, "STUDY_DIR", tmp_path / "study")
    base = {"study_consent": True, "pip_state": {}, "pip_scoring": {}, "onet_state": {}, "feeling": {}}
    a = dict(base, public_participant_id="SAME-CONTACT")
    b = dict(base, public_participant_id="SAME-CONTACT")
    pa.save_public_study_record(a)
    pa.save_public_study_record(b)
    assert a["public_study_id"] != b["public_study_id"]

def test_server_to_server_signature_uses_hmac_without_exposing_secret(monkeypatch, tmp_path):
    import clarte360_pip.connectors.gestion_actions as ga
    monkeypatch.setattr(ga, "PERSISTENT_DATA_DIR", tmp_path)
    key = "test-only-signing-key-abcdefghijklmnopqrstuvwxyz"
    port = GestionActionsPort(key)
    path = port.publish_event("EN_COURS", {"beneficiary_id": "BEN-1", "action_id": "ACT-1", "prescription_id": "PRE-1"})
    envelope = json.loads(path.read_text(encoding="utf-8"))
    headers = port.signed_delivery_headers(envelope)
    assert headers["X-Clarte360-Signature"].startswith("sha256=")
    assert key not in json.dumps(headers)
    assert key not in path.read_text(encoding="utf-8")
