from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from clarte360_cp.framework.config import BACKUP_RETENTION_DAYS, TECHNICAL_LOG_RETENTION_DAYS, FOLLOWUP_MAX_RETENTION_YEARS
from clarte360_cp.framework.security import minimize_log_fields
from clarte360_cp.framework.timeout import is_timed_out

ROOT=Path(__file__).resolve().parents[1]


def test_retention_constants_match_go17():
    assert BACKUP_RETENTION_DAYS==30
    assert TECHNICAL_LOG_RETENTION_DAYS==365
    assert FOLLOWUP_MAX_RETENTION_YEARS==3


def test_log_minimization_drops_sensitive_content():
    x=minimize_log_fields({"case_id":"C1","cv":"secret","token":"abc","prompt":"full","status":"OK"})
    assert x=={"case_id":"C1","status":"OK"}


def test_timeout_detects_expiry():
    now=datetime.now(timezone.utc)
    old=(now-timedelta(minutes=16)).isoformat()
    assert is_timed_out(old,now=now,limit_minutes=15)
    assert not is_timed_out((now-timedelta(minutes=1)).isoformat(),now=now,limit_minutes=15)


def test_no_real_secrets_or_tokens_in_source_tree():
    for p in (ROOT / "clarte360_cp").rglob("*.py"):
        text=p.read_text(encoding="utf-8")
        assert "BEGIN PRIVATE KEY" not in text
        assert "client_secret =" not in text


def test_app_has_no_public_mode():
    text=(ROOT/"clarte360_cp/ui/entry.py").read_text(encoding="utf-8")
    assert 'mode", "")).lower() != "accompagnement"' in text
    assert "PUBLIC" not in text
