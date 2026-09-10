from datetime import datetime, timedelta

from clarte360_pip.framework.timeout import is_timed_out


def test_timeout_boundary():
    now = datetime(2026, 9, 10, 10, 0, 0)
    assert is_timed_out((now - timedelta(minutes=16)).isoformat(), now=now, limit_minutes=15)
    assert not is_timed_out((now - timedelta(minutes=14)).isoformat(), now=now, limit_minutes=15)
