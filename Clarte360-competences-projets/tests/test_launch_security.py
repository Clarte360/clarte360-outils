from __future__ import annotations

import time
import pytest

from clarte360_cp.connectors.gestion_actions import LaunchTokenError, build_launch_token, verify_launch_token
from .helpers import KEY, payload


def verify(p):
    return verify_launch_token(build_launch_token(p, KEY), KEY, now_epoch=p["iat"])


def test_valid_accompanist_token():
    p = payload()
    c = verify(p)
    assert c.actor_role.value == "ACCOMPAGNATEUR"
    assert c.actor_id == "USR-1"
    assert c.prescription_id == "PRE-1"


def test_valid_beneficiary_token():
    p = payload(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT"], actor="BEN-ACTOR")
    c = verify(p)
    assert c.actor_role.value == "BENEFICIAIRE"


def test_bad_signature_rejected():
    p = payload(); token = build_launch_token(p, KEY)
    with pytest.raises(LaunchTokenError):
        verify_launch_token(token + "x", KEY, now_epoch=p["iat"])


def test_expired_rejected():
    p = payload(); p["iat"] = int(time.time()) - 1000; p["exp"] = p["iat"] + 600
    with pytest.raises(LaunchTokenError):
        verify_launch_token(build_launch_token(p, KEY), KEY, now_epoch=int(time.time()))


def test_ttl_above_900_rejected():
    p = payload(); p["exp"] = p["iat"] + 901
    with pytest.raises(LaunchTokenError): verify(p)


def test_wrong_tool_rejected():
    p = payload(); p["tool_id"] = "PIP_RIASEC"
    with pytest.raises(LaunchTokenError): verify(p)


def test_wrong_scope_vocab_rejected():
    p = payload(); p["scope_vocab"] = "PIP_V1"
    with pytest.raises(LaunchTokenError): verify(p)


def test_wrong_hub_rejected():
    p = payload(); p["hub_source"] = "OTHER"
    with pytest.raises(LaunchTokenError): verify(p)


def test_civil_identity_rejected():
    p = payload(); p["email"] = "x@example.org"
    with pytest.raises(LaunchTokenError): verify(p)


def test_beneficiary_cannot_escalate_scope():
    p = payload(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_WRITE"])
    with pytest.raises(LaunchTokenError): verify(p)


def test_accompanist_scopes_include_full_contract():
    scopes = [
        "CP_CASE_OPEN","CP_CASE_READ","CP_CASE_WRITE","CP_SOURCE_GDA_READ",
        "CP_SOURCE_MANUAL_IMPORT","CP_VALIDATE","CP_PUBLISH","CP_FINALIZE","CP_DELIVERABLE_RETURN",
    ]
    p = payload(scopes=scopes)
    c = verify(p)
    assert set(c.scopes) == set(scopes)
