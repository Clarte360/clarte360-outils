import base64, hashlib, hmac, json, time
import pandas as pd
import pytest

from validation import (
    ValidationError, access_code, clean_text, decode_json_bytes, email, finite_number,
    name, phone, safe_id, validate_state,
)
from hub_contract import verify_launch_token, status_event


def legacy_payload():
    order=[f"Q{i:03d}" for i in range(1,61)]
    return {
        "outil":"clarte360_preferences_professionnelles",
        "version":"1.9.4-socle-clarte360",
        "session_id":"abc-123",
        "passation_id":"CL360-PP-20260705-ABC12345",
        "beneficiaire":{"nom":"O'Connor","prenom":"Jean-Pierre","email":"jp@example.fr"},
        "started_at":"2026-07-05T10:00:00",
        "saved_at":"2026-07-05T10:15:00",
        "completed":False,
        "current_index":2,
        "question_order_displayed":order,
        "option_orders_displayed":{qid:["A","B","C","D"] for qid in order},
        "answers":{"Q001":"A","Q002":"D"},
        "access":{"sessions":[],"sauvegardes":[]},
    }


def token(payload, secret="secret-tres-long"):
    raw=json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()
    p=base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig=hmac.new(secret.encode(),p.encode(),hashlib.sha256).digest()
    s=base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return p+"."+s


def hub_payload(now=None):
    n=int(time.time() if now is None else now)
    return {
        "tool_id":"preferences-professionnelles","hub_source":"GESTION_ACTIONS_I9_H1",
        "role":"intervenant","beneficiary_id":"BEN-1","action_id":"ACT-1",
        "participant_id":"PAR-1","prescription_id":"PRE-1",
        "iat":n-10,"exp":n+3600,"scopes":["PREFERENCES_RUN","PREFERENCES_STATUS"]
    }

@pytest.mark.parametrize("value", ["O'Connor","Jean-Pierre","Élodie","Łukasz","Anne Marie","D’Angelo"])
def test_valid_names(value):
    assert name(value)==value

@pytest.mark.parametrize("value", ["Jean2","<script>","😀","../Paul","   "])
def test_invalid_names(value):
    with pytest.raises(ValidationError): name(value)

@pytest.mark.parametrize("value", ["a.b@example.com","prenom+tag@domaine.fr","x@y.co"])
def test_valid_emails(value):
    assert email(value)==value.lower()

@pytest.mark.parametrize("value", ["sans-arobase.fr","a@","a@b","a b@c.fr","a@b.fr,xx@y.fr","a@b.fr\nBcc:x@y.fr"])
def test_invalid_emails(value):
    with pytest.raises(ValidationError): email(value)

@pytest.mark.parametrize("value", ["+33 6 12 34 56 78","06 12 34 56 78","+36 (30) 123-4567"])
def test_valid_phones(value):
    assert phone(value)==value

@pytest.mark.parametrize("value", ["ABC123","123","+12345678901234567"])
def test_invalid_phones(value):
    with pytest.raises(ValidationError): phone(value)

def test_clean_text_control_and_length():
    with pytest.raises(ValidationError): clean_text("abc\x00def")
    with pytest.raises(ValidationError): clean_text("x"*161,max_len=160)
    assert clean_text("  bonjour  ")=="bonjour"

def test_access_code():
    assert access_code("123456")=="123456"
    for bad in ["12345","1234567","12A456",""]:
        with pytest.raises(ValidationError): access_code(bad)

def test_safe_id():
    assert safe_id("ACT-2026_01:ABC")=="ACT-2026_01:ABC"
    for bad in ["../etc/passwd","a/b","x"*161]:
        with pytest.raises(ValidationError): safe_id(bad)

def test_legacy_194_json_is_accepted():
    p=legacy_payload()
    assert decode_json_bytes(json.dumps(p).encode(),allow_completed=False)["version"]=="1.9.4-socle-clarte360"

def test_json_completed_refused_for_resume():
    p=legacy_payload(); p["completed"]=True
    with pytest.raises(ValidationError): decode_json_bytes(json.dumps(p).encode(),allow_completed=False)

def test_json_bad_encoding_and_size():
    with pytest.raises(ValidationError): decode_json_bytes(b"\xff\xfe")
    with pytest.raises(ValidationError): decode_json_bytes(b"x"*(2*1024*1024+1))

def test_json_bad_question_and_option():
    p=legacy_payload(); p["question_order_displayed"][0]="../Q001"
    with pytest.raises(ValidationError): validate_state(p)
    p=legacy_payload(); p["answers"]["Q001"]="Z"
    with pytest.raises(ValidationError): validate_state(p)

def test_json_duplicate_question_order():
    p=legacy_payload(); p["question_order_displayed"][1]="Q001"
    with pytest.raises(ValidationError): validate_state(p)

def test_json_unknown_tool():
    p=legacy_payload(); p["outil"]="autre_outil"
    with pytest.raises(ValidationError): validate_state(p)

def test_json_invalid_beneficiary():
    p=legacy_payload(); p["beneficiaire"]["nom"]="Dupont42"
    with pytest.raises(ValidationError): validate_state(p)

def test_finite_number():
    assert finite_number("2.5","Score",0,3)==2.5
    for bad in [float("nan"),float("inf"),-1,4]:
        with pytest.raises(ValidationError): finite_number(bad,"Score",0,3)

def test_questionnaire_file_structure():
    df=pd.read_excel("data/questions_preferences_professionnelles_v1.xlsx",sheet_name="Questions")
    active=df[df["Statut"].astype(str).str.strip().str.lower()=="active"]
    assert len(active)==60
    assert active["ID"].astype(str).str.fullmatch(r"Q\d{3}").all()
    assert active["ID"].nunique()==60
    assert set(active["Dimension"])=={f"PP{i}" for i in range(1,11)}
    assert active.groupby("Dimension").size().eq(6).all()
    for col in ["Question","Reponse A","Reponse B","Reponse C","Reponse D"]:
        assert active[col].astype(str).str.strip().ne("").all()
    for col in ["Score A","Score B","Score C","Score D","Max question"]:
        nums=pd.to_numeric(active[col],errors="raise")
        assert nums.notna().all()

def test_hub_valid_token_admin_and_intervenant():
    n=2_000_000_000
    for role in ["admin","intervenant"]:
        p=hub_payload(n); p["role"]=role
        assert verify_launch_token(token(p),"secret-tres-long",now=n)["role"]==role

def test_hub_rejects_beneficiary_as_prescriber():
    n=2_000_000_000; p=hub_payload(n); p["role"]="beneficiaire"
    with pytest.raises(ValidationError): verify_launch_token(token(p),"secret-tres-long",now=n)

def test_hub_rejects_bad_signature():
    n=2_000_000_000; t=token(hub_payload(n),"secret-a")
    with pytest.raises(ValidationError): verify_launch_token(t,"secret-b",now=n)

def test_hub_rejects_expired_and_long_lifetime():
    n=2_000_000_000
    p=hub_payload(n); p["exp"]=n-1
    with pytest.raises(ValidationError): verify_launch_token(token(p),"secret-tres-long",now=n)
    p=hub_payload(n); p["iat"]=n; p["exp"]=n+8*86400
    with pytest.raises(ValidationError): verify_launch_token(token(p),"secret-tres-long",now=n)

def test_hub_rejects_wrong_tool_scope_and_traversal():
    n=2_000_000_000
    p=hub_payload(n); p["tool_id"]="roue-valeurs"
    with pytest.raises(ValidationError): verify_launch_token(token(p),"secret-tres-long",now=n)
    p=hub_payload(n); p["scopes"]=["PREFERENCES_STATUS"]
    with pytest.raises(ValidationError): verify_launch_token(token(p),"secret-tres-long",now=n)
    p=hub_payload(n); p["action_id"]="../ACT"
    with pytest.raises(ValidationError): verify_launch_token(token(p),"secret-tres-long",now=n)

def test_status_event_minimal_no_scores_or_answers():
    p=hub_payload(2_000_000_000)
    event=status_event(p,"completed","DOC-123")
    assert event["status"]=="completed"
    assert event["document_ref"]=="DOC-123"
    assert "answers" not in event and "scores" not in event

from guard_state import fingerprint as guard_fingerprint, is_dirty as guard_is_dirty


def _guard_state():
    return {
        "test_started": True,
        "beneficiaire": {"nom":"Dupont","prenom":"Anne","email":"anne@example.fr"},
        "answers": {"Q001":"A"},
        "current_index": 1,
        "question_order": ["Q001","Q002"],
        "option_orders": {"Q001":["A","B","C","D"],"Q002":["A","B","C","D"]},
    }


def test_guard_dirty_until_first_json_save():
    state=_guard_state()
    assert guard_is_dirty(state, None) is True
    saved=guard_fingerprint(state)
    assert guard_is_dirty(state, saved) is False


def test_guard_rearms_after_answer_change():
    state=_guard_state(); saved=guard_fingerprint(state)
    state["answers"]["Q002"]="C"; state["current_index"]=2
    assert guard_is_dirty(state, saved) is True


def test_guard_detects_unvalidated_radio_selection():
    state=_guard_state(); saved=guard_fingerprint(state)
    state["radio_Q002"]="Une proposition en cours"
    assert guard_is_dirty(state, saved) is True


def test_guard_ignores_traceability_noise():
    state=_guard_state(); saved=guard_fingerprint(state)
    state["access"]={"last_seen_at":"2026-09-12T18:00:00","sessions":[{"duration_seconds":99}]}
    state["email_sent"]=True
    assert guard_is_dirty(state, saved) is False


def test_guard_inactive_before_questionnaire_start():
    state=_guard_state(); state["test_started"]=False
    assert guard_is_dirty(state, None) is False
