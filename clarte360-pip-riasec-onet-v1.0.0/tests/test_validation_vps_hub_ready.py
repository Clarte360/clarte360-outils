import json
from pathlib import Path

import pytest

from clarte360_pip.connectors.gestion_actions import LaunchTokenError, build_launch_token, verify_launch_token
from clarte360_pip.framework.app_identity import load_app_identity
from clarte360_pip.framework.persistence import decode_snapshot_bytes, restore_snapshot
from clarte360_pip.framework.public_access import validate_public_identity
from clarte360_pip.framework.validation import (
    ValidationError,
    reject_spreadsheet_formula,
    validate_access_code,
    validate_email,
    validate_person_name,
    validate_phone,
    validate_safe_id,
    validate_score,
    validate_https_url,
)

KEY = "test-only-signing-key-abcdefghijklmnopqrstuvwxyz"


def _hub_payload(**overrides):
    data = {
        "v": 2,
        "iat": 1_800_000_000,
        "exp": 1_800_003_600,
        "tool_id": "pip-riasec-onet",
        "hub_source": "GESTION_ACTIONS_I9_H1",
        "beneficiary_id": "BEN-1",
        "action_id": "CLA0003",
        "participant_id": "PART-1",
        "prescription_id": "PRESC-1",
        "beneficiary_first_name": "Alice",
        "beneficiary_last_name": "Martin",
        "action_number": "CLA0003",
        "action_title": "Bilan de compétences",
        "scopes": ["PIP_RUN", "PIP_RESUME", "PIP_STATUS"],
        "return_mode": "OUTBOX",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("value", ["O'Connor", "Jean-Pierre", "Élodie", "Łukasz", "Anne Marie"])
def test_legitimate_international_names_are_accepted(value):
    assert validate_person_name(value, "Nom")


@pytest.mark.parametrize("value", ["Jean123", "<script>", "😀", "   ", "../etc"])
def test_bad_names_are_rejected(value):
    with pytest.raises(ValidationError):
        validate_person_name(value, "Nom")


@pytest.mark.parametrize("value", ["dominique@example.fr", "prenom.nom+tag@example.co.uk"])
def test_valid_emails(value):
    assert validate_email(value) == value.lower()


@pytest.mark.parametrize("value", ["sans-arobase.fr", "a@", "a@b", "a@b.fr\r\nBcc:x@y.fr", "a@b.fr;c@d.fr"])
def test_bad_emails_rejected(value):
    with pytest.raises(ValidationError):
        validate_email(value)


@pytest.mark.parametrize("value", ["+33 6 12 34 56 78", "+36 (30) 123-4567", "01.89.48.08.25"])
def test_valid_phones(value):
    assert validate_phone(value)


@pytest.mark.parametrize("value", ["123", "1234567890123456", "06AB123456", "33+612345678"])
def test_bad_phones_rejected(value):
    with pytest.raises(ValidationError):
        validate_phone(value)


def test_public_identity_reports_all_missing_required_fields():
    errors = validate_public_identity({"first_name":"", "last_name":"", "phone":"", "email":""})
    assert len(errors) == 4


@pytest.mark.parametrize("value", [0, 6, -1, 2.5, "abc", float("nan"), float("inf")])
def test_score_bounds_rejected(value):
    with pytest.raises(ValidationError):
        validate_score(value, "score")


def test_safe_ids_reject_path_traversal_and_spaces():
    for value in ["../etc", "A/B", "A B", "x" * 161]:
        with pytest.raises(ValidationError):
            validate_safe_id(value, "id")


def test_access_code_requires_six_digits():
    assert validate_access_code("123456") == "123456"
    for value in ["12345", "1234567", "12A456"]:
        with pytest.raises(ValidationError):
            validate_access_code(value)


def test_url_only_allows_https_without_credentials():
    assert validate_https_url("https://pip-riasec.clarte360.com")
    for value in ["javascript:alert(1)", "http://example.com", "https://user:pass@example.com", "not-a-url"]:
        with pytest.raises(ValidationError):
            validate_https_url(value)


def test_excel_formula_prefixes_are_rejected():
    for value in ["=HYPERLINK('x')", "+CMD", "-1+2", "@SUM(A1:A2)"]:
        with pytest.raises(ValidationError):
            reject_spreadsheet_formula(value)


def test_snapshot_upload_rejects_malformed_empty_and_oversized_json():
    for raw in [b"", b"{bad", b"[]"]:
        with pytest.raises(ValidationError):
            decode_snapshot_bytes(raw)
    with pytest.raises(ValidationError):
        decode_snapshot_bytes(b"{" + b"x" * (2 * 1024 * 1024) + b"}")


def test_snapshot_restore_rejects_bad_score_and_traversal_id():
    payload = {
        "schema": "clarte360.pip.run.v1",
        "passation_id": "../bad",
        "journey": "PIP_SEUL",
        "pip_state": {"index": 0, "answers": {"Q1": 9}},
        "onet_state": {},
        "public_identity": {},
        "session_history": [],
    }
    with pytest.raises(ValidationError):
        restore_snapshot(payload, {})


def test_i9_h1_scopes_contract_is_accepted():
    token = build_launch_token(_hub_payload(), KEY)
    ctx = verify_launch_token(token, KEY, now_epoch=1_800_000_100)
    assert ctx.raw["tool_id"] == "pip-riasec-onet"
    assert ctx.raw["hub_source"] == "GESTION_ACTIONS_I9_H1"
    assert "PIP_RUN" in ctx.rights


def test_i9_h1_wrong_tool_unknown_scope_and_missing_run_are_rejected():
    bad_payloads = [
        _hub_payload(tool_id="other-tool"),
        _hub_payload(scopes=["PIP_RUN", "ADMIN_ALL"]),
        _hub_payload(scopes=["PIP_STATUS"]),
    ]
    for payload in bad_payloads:
        with pytest.raises(LaunchTokenError):
            verify_launch_token(build_launch_token(payload, KEY), KEY, now_epoch=1_800_000_100)


def test_app_identity_is_versioned_and_points_to_current_clarte_url():
    data = load_app_identity()
    assert data["tool_id"] == "pip-riasec-onet"
    assert data["production_url"] == "https://pip-riasec.clarte360.com"
    assert data["hub_compatible"] is True


def test_no_real_secret_in_app_identity():
    text = Path("config/app_identity.json").read_text(encoding="utf-8").lower()
    for word in ["password", "api_key", "signing_key", "secret"]:
        assert word not in text
