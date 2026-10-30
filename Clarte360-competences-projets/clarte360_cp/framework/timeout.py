from __future__ import annotations

from datetime import datetime, timezone


def is_timed_out(last_activity_at: str | None, *, now: datetime | None = None, limit_minutes: int = 60) -> bool:
    if not last_activity_at:
        return False
    try:
        last = datetime.fromisoformat(last_activity_at)
    except (TypeError, ValueError):
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    elapsed = (current - last).total_seconds()
    return elapsed < 0 or elapsed >= limit_minutes * 60
