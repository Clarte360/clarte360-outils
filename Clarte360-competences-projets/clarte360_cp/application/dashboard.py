from __future__ import annotations

from dataclasses import dataclass

from clarte360_cp.domain.sources import ACCEPTED_SOURCE_TYPES
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.dashboard import DashboardRepository, DashboardSnapshot


@dataclass(frozen=True)
class AccompanistDashboardView:
    snapshot: DashboardSnapshot
    introduced_sources: int
    total_sources: int


def build_accompanist_dashboard(case_id: str, *, database_url: str | None = None) -> AccompanistDashboardView:
    engine = build_engine(database_url)
    Factory = session_factory(engine)
    with Factory() as session:
        snapshot = DashboardRepository(session).load(case_id)
    introduced = sum(1 for item in snapshot.document_summaries if item.present)
    return AccompanistDashboardView(
        snapshot=snapshot,
        introduced_sources=introduced,
        total_sources=len(ACCEPTED_SOURCE_TYPES),
    )
