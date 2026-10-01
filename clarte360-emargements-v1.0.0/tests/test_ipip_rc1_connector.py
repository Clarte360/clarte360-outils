import base64
import hashlib
import hmac
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import services


KEY = "K" * 48


def _decode_payload(token):
    part = token.split(".", 1)[0]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)).decode("utf-8"))


def test_registry_contains_ipip_rc1():
    data = json.loads((Path(__file__).parents[1] / "config" / "tool_registry.json").read_text(encoding="utf-8"))
    row = next(x for x in data["tools"] if x["tool_code"] == "IPIP_NEO120")
    assert row["base_url"] == "https://ipip-neo120.clarte360.com"
    assert row["tool_version"] == "0.7.0-rc1"
    assert row["launch_type"] == "EXTERNAL_SIGNED"
    assert row["prescription_allowed"] is True


def test_ipip_launch_token_contract_has_no_civil_identity(monkeypatch):
    row = {
        "tool_code": "IPIP_NEO120",
        "status": "EN_COURS",
        "base_url": "https://ipip-neo120.clarte360.com",
        "beneficiary_id": 12,
        "action_id": 34,
        "participant_id": 56,
        "prescription_id": "PR-IPIP-1",
    }
    monkeypatch.setattr(services, "one", lambda *a, **k: row)
    url = services.build_ipip_prescription_launch(None, "PR-IPIP-1", KEY, valid_seconds=900)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert qs["mode"] == ["accompagnement"]
    token = qs["launch"][0]
    payload = _decode_payload(token)
    assert payload["tool_id"] == "ipip-neo120"
    assert payload["hub_source"] == "GESTION_ACTIONS_I9_H1"
    assert set(payload["scopes"]) == {"IPIP_RUN", "IPIP_RESUME", "IPIP_STATUS", "IPIP_RESULT_READ"}
    assert payload["beneficiary_id"] == "12"
    assert payload["action_id"] == "34"
    assert payload["participant_id"] == "56"
    assert payload["prescription_id"] == "PR-IPIP-1"
    assert "beneficiary" not in payload
    assert "email" not in json.dumps(payload).lower()
    assert "first_name" not in payload
    assert "last_name" not in payload
    pp, sp = token.split(".", 1)
    expected = hmac.new(KEY.encode(), pp.encode("ascii"), hashlib.sha256).digest()
    supplied = base64.urlsafe_b64decode(sp + "=" * (-len(sp) % 4))
    assert hmac.compare_digest(expected, supplied)


def test_ipip_termine_requires_report(monkeypatch, tmp_path):
    pr = {
        "id": 1,
        "tool_code": "IPIP_NEO120",
        "prescription_id": "PR-IPIP-1",
        "beneficiary_id": "12",
        "action_id": "34",
        "participant_id": "56",
        "status": "EN_COURS",
        "result_refs_json": "[]",
    }
    def fake_one(engine, sql, params=None):
        if "prescription_events" in sql:
            return None
        if "tool_prescriptions" in sql:
            return pr
        return None
    monkeypatch.setattr(services, "one", fake_one)
    event = {
        "event_id": "evt-ipip-1",
        "event_type": "TERMINE",
        "tool_id": "ipip-neo120",
        "payload": {
            "prescription_id": "PR-IPIP-1",
            "beneficiary_id": "12",
            "action_id": "34",
            "participant_id": "56",
            "passation_id": "run-1",
            "documents": [],
        },
    }
    try:
        services.process_ipip_accompaniment_event(None, event, tmp_path)
    except ValueError as exc:
        assert "Rapport IPIP absent" in str(exc)
    else:
        raise AssertionError("TERMINE sans rapport aurait dû être refusé")
