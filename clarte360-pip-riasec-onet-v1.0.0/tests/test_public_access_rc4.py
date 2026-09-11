from datetime import datetime, timedelta
from pathlib import Path
from clarte360_pip.framework.public_access import validate_public_identity, code_digest, verify_public_code, pseudonym_for

def test_public_identity_requires_all_fields_and_valid_email():
    good={"first_name":"Ada","last_name":"Lovelace","job_title":"Analyste","company":"Example","phone":"0102030405","email":"ada@example.org"}
    assert validate_public_identity(good)==[]
    bad=dict(good,email="bad")
    assert validate_public_identity(bad)

def test_access_code_verification_and_expiry():
    state={"digest":code_digest("123456"),"expires_at":(datetime.now()+timedelta(minutes=2)).isoformat(),"attempts":0}
    assert verify_public_code("123456",state)
    expired={"digest":code_digest("123456"),"expires_at":(datetime.now()-timedelta(minutes=2)).isoformat(),"attempts":0}
    assert not verify_public_code("123456",expired)

def test_study_pseudonym_is_stable_and_not_raw_id():
    p=pseudonym_for("participant-123")
    assert p==pseudonym_for("participant-123")
    assert "participant-123" not in p
