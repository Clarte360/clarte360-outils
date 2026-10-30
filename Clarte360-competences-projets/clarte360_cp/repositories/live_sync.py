from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AuditEvent, Case, IntersessionTask, PhaseState, PublicationEvent, Validation


@dataclass(frozen=True)
class LiveSyncSnapshot:
    case_id: str
    revision: str
    latest_change_at: datetime | None
    latest_probe_at: datetime | None
    latest_probe_actor: str | None
    latest_probe_label: str | None
    probe_count: int


class LiveSyncRepository:
    """Lecture légère de fraîcheur inter-session + sonde synthétique de recette GO-21."""

    def __init__(self, session: Session):
        self.session = session

    def snapshot(self, case_id: str) -> LiveSyncSnapshot:
        case = self.session.get(Case, case_id)
        if case is None:
            raise KeyError(case_id)

        timestamps = [case.updated_at]
        for model, column in (
            (PhaseState, PhaseState.updated_at),
            (Validation, Validation.at),
            (PublicationEvent, PublicationEvent.published_at),
            (IntersessionTask, IntersessionTask.created_at),
            (AuditEvent, AuditEvent.timestamp),
        ):
            value = self.session.scalar(select(func.max(column)).where(model.case_id == case_id))
            if value is not None:
                timestamps.append(value)
        latest = max(timestamps) if timestamps else None

        counts = []
        for model in (PhaseState, Validation, PublicationEvent, IntersessionTask, AuditEvent):
            counts.append(int(self.session.scalar(select(func.count()).select_from(model).where(model.case_id == case_id)) or 0))
        revision = f"{case.row_version}:" + ":".join(str(v) for v in counts) + f":{latest.isoformat() if latest else '-'}"

        probe = self.session.scalar(
            select(AuditEvent)
            .where(AuditEvent.case_id == case_id, AuditEvent.event_type == "GO21_SYNC_PROBE")
            .order_by(AuditEvent.timestamp.desc())
            .limit(1)
        )
        probe_count = int(self.session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.case_id == case_id,
                AuditEvent.event_type == "GO21_SYNC_PROBE",
            )
        ) or 0)
        label = None
        actor = None
        at = None
        if probe is not None:
            at = probe.timestamp
            actor = probe.actor_type
            try:
                label = str(json.loads(probe.metadata_json_minimized or "{}").get("label") or "") or None
            except Exception:
                label = None

        return LiveSyncSnapshot(case_id, revision, latest, at, actor, label, probe_count)

    def record_probe(self, case_id: str, *, actor_type: str, actor_id: str, label: str) -> LiveSyncSnapshot:
        clean = " ".join((label or "signal").split())[:120]
        event = AuditEvent(
            audit_event_id=str(uuid4()),
            case_id=case_id,
            event_type="GO21_SYNC_PROBE",
            object_type="CASE",
            object_id=case_id,
            object_version=None,
            actor_type=actor_type,
            actor_id=actor_id,
            metadata_json_minimized=json.dumps({"label": clean}, ensure_ascii=False, separators=(",", ":")),
        )
        self.session.add(event)
        self.session.commit()
        return self.snapshot(case_id)
