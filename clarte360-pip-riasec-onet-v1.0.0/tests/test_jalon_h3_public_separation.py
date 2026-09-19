import json
from pathlib import Path

import pytest

from clarte360_pip.connectors.gestion_actions import (
    GestionActionsPort,
    PUBLIC_CRM_EVENT_TYPES,
    PUBLIC_CRM_FORBIDDEN_KEYS,
)
from clarte360_pip.framework.public_access import save_public_study_record, STUDY_SCHEMA


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_h3_public_crm_events_accept_only_separated_commercial_payload(monkeypatch, tmp_path):
    import clarte360_pip.connectors.gestion_actions as ga
    monkeypatch.setattr(ga, "PERSISTENT_DATA_DIR", tmp_path)
    port = GestionActionsPort(None)
    base = {
        "source": "PIP_PUBLIC",
        "first_name": "Test",
        "last_name": "Public",
        "email": "test@example.org",
        "phone": "0600000000",
        "job_title": "Direction",
        "company": "Exemple",
        "interests": ["PIP-RIASEC"],
        "marketing_opt_in": False,
        "rgpd_text_version": "RGPD-TEST",
    }
    for event_type in PUBLIC_CRM_EVENT_TYPES:
        payload = dict(base)
        if event_type == "CONTACT_EMAIL_VERIFIED":
            payload["email_verified_at"] = "2026-09-19T12:00:00+00:00"
        if event_type == "CALLBACK_REQUESTED":
            payload.update(requested_at="2026-09-19T12:30:00+00:00", reason="ECHANGER_RESULTATS_OU_PROJET")
        path = port.publish_event(event_type, payload)
        envelope = _read(path)
        exported = envelope["payload"]
        assert exported["email"] == "test@example.org"
        assert "PIP-RIASEC" in exported["interests"]
        assert not (set(exported) & PUBLIC_CRM_FORBIDDEN_KEYS)


def test_h3_public_crm_rejects_every_forbidden_join_or_research_key(monkeypatch, tmp_path):
    import clarte360_pip.connectors.gestion_actions as ga
    monkeypatch.setattr(ga, "PERSISTENT_DATA_DIR", tmp_path)
    port = GestionActionsPort(None)
    for key in sorted(PUBLIC_CRM_FORBIDDEN_KEYS):
        with pytest.raises(ValueError, match="clé interdite"):
            port.publish_event("CONTACT_UPDATED", {"source": "PIP_PUBLIC", "email": "x@example.org", key: "X"})


def test_h3_public_crm_rejects_forbidden_key_even_when_nested(monkeypatch, tmp_path):
    import clarte360_pip.connectors.gestion_actions as ga
    monkeypatch.setattr(ga, "PERSISTENT_DATA_DIR", tmp_path)
    with pytest.raises(ValueError, match="participant_id"):
        GestionActionsPort(None).publish_event(
            "CALLBACK_REQUESTED",
            {"source": "PIP_PUBLIC", "email": "x@example.org", "meta": {"participant_id": "PUB-1"}},
        )


def test_h3_pages_do_not_export_internal_public_participant_id_to_crm():
    src = Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")
    contact = src[src.index("def _public_contact_payload"):src.index("def _publish_public_contact_event")]
    callback = src[src.index("callback_payload = {"):src.index('GestionActionsPort(None).publish_event("CALLBACK_REQUESTED"')]
    assert '"participant_id"' not in contact
    assert '"participant_id"' not in callback
    assert '"source": "PIP_PUBLIC"' in contact
    assert '"source": "PIP_PUBLIC"' in callback
    assert '"email"' in callback and '"requested_at"' in callback and '"reason"' in callback


def test_h3_study_record_matches_gestion_contract_and_has_no_crm_join_key(monkeypatch, tmp_path):
    import clarte360_pip.framework.public_access as pa
    monkeypatch.setattr(pa, "STUDY_DIR", tmp_path / "study")
    state = {
        "study_consent": True,
        "public_participant_id": "CRM-CONTACT-INTERNAL",
        "passation_id": "PASS-INTERNAL",
        "public_identity": {"first_name": "Dominique", "last_name": "Test", "email": "secret@example.org", "phone": "0600000000"},
        "journey": "PIP_PUIS_ONET60",
        "onet_selected_timing": "POST_PIP_RESULTS",
        "pip_state": {"bank_version": "PIP-BANK-0.5", "answers": {"PIP-1": 5}},
        "pip_scoring": {"algorithm_version": "PIP-SCORE-0.5", "indices": {"R": 50}, "order": ["R"]},
        "onet_state": {"completed": True, "instrument": "O*NET Interest Profiler", "answers": {"1": 3}, "results": [{"code": "realistic", "score": 20}]},
        "feeling": {"answers": {"global": 4}},
    }
    path = save_public_study_record(state)
    assert path is not None and path.parent == tmp_path / "study"
    payload = _read(path)
    raw = json.dumps(payload, ensure_ascii=False)
    assert payload["schema"] == STUDY_SCHEMA == "clarte360.pip.public-study.v1"
    assert payload["study_id"] and path.stem == payload["study_id"]
    assert payload["pip_bank_version"] == "PIP-BANK-0.5"
    assert payload["pip_scoring_version"] == "PIP-SCORE-0.5"
    assert payload["pip_answers"] == {"PIP-1": 5}
    assert payload["study_consent"] is True
    for forbidden_value in ("CRM-CONTACT-INTERNAL", "PASS-INTERNAL", "Dominique", "secret@example.org", "0600000000"):
        assert forbidden_value not in raw
    forbidden_keys = {
        "first_name", "last_name", "email", "phone", "identity", "public_identity", "crm_id", "contact_id",
        "beneficiary_id", "action_id", "participant_id", "public_participant_id", "prescription_id", "passation_id", "source_ref",
    }
    def keys(v):
        if isinstance(v, dict):
            for k, x in v.items():
                yield k
                yield from keys(x)
        elif isinstance(v, list):
            for x in v:
                yield from keys(x)
    assert not (set(keys(payload)) & forbidden_keys)


def test_h3_study_id_is_unique_even_for_same_internal_contact(monkeypatch, tmp_path):
    import clarte360_pip.framework.public_access as pa
    monkeypatch.setattr(pa, "STUDY_DIR", tmp_path / "study")
    base = {"study_consent": True, "public_participant_id": "SAME", "pip_state": {}, "pip_scoring": {}, "onet_state": {}, "feeling": {}}
    a, b = dict(base), dict(base)
    pa.save_public_study_record(a)
    pa.save_public_study_record(b)
    assert a["public_study_id"] != b["public_study_id"]


def test_h3_no_study_file_without_research_consent(monkeypatch, tmp_path):
    import clarte360_pip.framework.public_access as pa
    monkeypatch.setattr(pa, "STUDY_DIR", tmp_path / "study")
    result = pa.save_public_study_record({"study_consent": False, "pip_state": {}, "pip_scoring": {}})
    assert result is None
    assert not (tmp_path / "study").exists()


def test_h3_active_outbox_path_is_single_and_documented_in_code():
    src = Path("clarte360_pip/connectors/gestion_actions.py").read_text(encoding="utf-8")
    assert 'PERSISTENT_DATA_DIR / "connector_outbox" / "gestion_actions"' in src
    assert 'PERSISTENT_DATA_DIR / "connector_outbox" / "gestion_actions_events.jsonl"' not in src
    assert 'audit = _outbox_root() / "events.jsonl"' in src


def test_h3_keeps_h2_report_before_feeling_intent():
    src = Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")
    assert "_render_pip_report_preview_before_feeling" in src
    assert "pdf_pages_as_png(pdf_bytes, 3, 4)" in src
    assert "J’ai consulté ma synthèse — donner mon ressenti" in src
