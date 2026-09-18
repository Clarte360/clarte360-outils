
import base64
import json
from urllib.parse import urlparse, parse_qs
from sqlalchemy import create_engine

from db import init_db
from services import (
    seed_tool_catalog, create_action, add_participant, create_beneficiary,
    link_participant_to_beneficiary, create_tool_prescription,
    build_pip_prescription_launch, execute,
)

KEY = "test-signing-key-for-pip-rc8-123456789"
EXPECTED = {"PIP_RUN", "PIP_RESUME", "PIP_STATUS", "PIP_RESULT_READ"}

def _engine():
    e = create_engine("sqlite:///:memory:", future=True)
    init_db(e)
    seed_tool_catalog(e)
    return e

def _decode(token):
    part = token.split(".", 1)[0]
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part.encode()).decode())

def test_pip_prescription_launch_uses_current_110_scopes():
    e = _engine()
    aid = create_action(e,{
        "action_no":"RC8-001","title":"PIP RC8","subtitle":None,"nature":"FORMATION",
        "mode":"INDIVIDUEL","client_name":"Client","client_type":"Particulier",
        "group_code":None,"planned_hours":1,"expected_participants":1,
        "admin_email":"admin@example.org","trainer_name":None,"trainer_email":None,
        "location":"Online","notes":None,"source":"TEST"},"test")
    execute(e,"UPDATE actions SET prestation_type='FORMATION' WHERE id=:a",{"a":aid})
    pid,_ = add_participant(e,aid,{"last_name":"TEST","first_name":"Alice","birth_date":"1990-01-01","email":"alice@example.org"},"test")
    bid = create_beneficiary(e,"TEST","Alice","1990-01-01","alice@example.org",actor="test")
    link_participant_to_beneficiary(e,pid,bid,"test")
    pr = create_tool_prescription(e,"PIP_RIASEC_ONET",bid,aid,pid,actor="test")
    url = build_pip_prescription_launch(e,pr["prescription_id"],KEY)
    token = parse_qs(urlparse(url).query)["launch"][0]
    payload = _decode(token)
    assert set(payload["rights"]) == EXPECTED
    assert "PIP_RIASEC" not in payload["rights"]
    assert "ONET60" not in payload["rights"]

def test_secret_names_are_not_changed_in_application_contract():
    app = open("app.py", encoding="utf-8").read()
    assert "pip_connector" in app
    assert "launch_signing_key" in app
