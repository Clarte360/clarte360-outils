from __future__ import annotations

from dataclasses import dataclass

from clarte360_cp.domain.launch import LaunchContext
from clarte360_cp.repositories import CaseRepository, build_engine, init_database, session_factory


@dataclass(frozen=True)
class BootstrapResult:
    case_id: str
    case_code: str
    row_version: int
    current_phase: int | None


def bootstrap_case(ctx: LaunchContext, *, database_url: str | None = None) -> BootstrapResult:
    engine = build_engine(database_url)
    init_database(engine)
    Factory = session_factory(engine)
    with Factory() as session:
        case = CaseRepository(session).open_or_create(ctx)
        return BootstrapResult(case.case_id, case.case_code, case.row_version, case.current_phase)
