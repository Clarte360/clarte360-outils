from __future__ import annotations

from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.live_sync import LiveSyncRepository, LiveSyncSnapshot


def build_live_sync(case_id: str, *, database_url: str | None = None) -> LiveSyncSnapshot:
    engine = build_engine(database_url)
    Factory = session_factory(engine)
    with Factory() as session:
        return LiveSyncRepository(session).snapshot(case_id)


def record_sync_probe(case_id: str, *, actor_type: str, actor_id: str, label: str, database_url: str | None = None) -> LiveSyncSnapshot:
    engine = build_engine(database_url)
    Factory = session_factory(engine)
    with Factory() as session:
        return LiveSyncRepository(session).record_probe(case_id, actor_type=actor_type, actor_id=actor_id, label=label)
