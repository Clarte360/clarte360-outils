from __future__ import annotations

import json
from sqlalchemy.orm import Session

from clarte360_cp.framework.security import minimize_log_fields
from .models import AuditEvent


def append_audit_event(session: Session, *, case_id: str, event_type: str, object_type: str, object_id: str, actor_type: str, actor_id: str, object_version: int | None = None, metadata: dict | None = None) -> AuditEvent:
    event = AuditEvent(
        case_id=case_id, event_type=event_type, object_type=object_type, object_id=object_id,
        object_version=object_version, actor_type=actor_type, actor_id=actor_id,
        metadata_json_minimized=json.dumps(minimize_log_fields(metadata or {}), ensure_ascii=False, separators=(",", ":")),
    )
    session.add(event); session.commit(); return event
