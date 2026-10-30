from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clarte360_cp.domain.sources import ACCEPTED_SOURCE_TYPES, FORBIDDEN_SOURCE_TYPES
from .models import (
    Artifact,
    ArtifactVersion,
    Case,
    ClosureRecord,
    IntersessionTask,
    PhaseState,
    ReviewFlag,
    Validation,
    OrientationState,
)


@dataclass(frozen=True)
class DocumentSummary:
    artifact_type: str
    label: str
    present: bool
    current_state: str | None
    version_no: int | None


@dataclass(frozen=True)
class DashboardSnapshot:
    case_id: str
    case_code: str
    case_status: str
    current_phase: int | None
    phase_states: tuple[tuple[int, str], ...]
    open_flags: int
    active_tasks: int
    submitted_tasks: int
    document_summaries: tuple[DocumentSummary, ...]
    other_documents_count: int
    last_validation_at: object | None
    closure_present: bool
    orientation_published: bool


class DashboardRepository:
    """Lecture seule des éléments nécessaires au shell Accompagnateur GO-20."""

    def __init__(self, session: Session):
        self.session = session

    def load(self, case_id: str) -> DashboardSnapshot:
        case = self.session.get(Case, case_id)
        if case is None:
            raise KeyError(case_id)

        phase_states = tuple(
            (p.phase_no, p.state)
            for p in self.session.scalars(
                select(PhaseState).where(PhaseState.case_id == case_id).order_by(PhaseState.phase_no)
            )
        )

        open_flags = int(self.session.scalar(
            select(func.count()).select_from(ReviewFlag).where(
                ReviewFlag.case_id == case_id,
                ReviewFlag.status == "OPEN",
            )
        ) or 0)

        active_tasks = int(self.session.scalar(
            select(func.count()).select_from(IntersessionTask).where(
                IntersessionTask.case_id == case_id,
                IntersessionTask.state.notin_(("CLOTUREE", "ANNULEE")),
            )
        ) or 0)
        submitted_tasks = int(self.session.scalar(
            select(func.count()).select_from(IntersessionTask).where(
                IntersessionTask.case_id == case_id,
                IntersessionTask.state.in_(("SOUMISE", "A_DEBRIEFER")),
            )
        ) or 0)

        artifacts = list(self.session.scalars(select(Artifact).where(Artifact.case_id == case_id)))
        by_type: dict[str, Artifact] = {}
        for artifact in artifacts:
            if artifact.artifact_type in FORBIDDEN_SOURCE_TYPES:
                continue
            by_type.setdefault(artifact.artifact_type, artifact)

        summaries: list[DocumentSummary] = []
        source_types = set(ACCEPTED_SOURCE_TYPES)
        for code in ACCEPTED_SOURCE_TYPES:
            label = code
            artifact = by_type.get(code)
            state = None
            version_no = None
            if artifact and artifact.current_version_id:
                version = self.session.get(ArtifactVersion, artifact.current_version_id)
                if version:
                    state = version.state
                    version_no = version.version_no
            summaries.append(DocumentSummary(code, label, artifact is not None, state, version_no))

        other_documents_count = sum(
            1 for a in artifacts if a.artifact_type not in source_types and a.artifact_type not in FORBIDDEN_SOURCE_TYPES
        )

        last_validation_at = self.session.scalar(
            select(Validation.at).where(Validation.case_id == case_id).order_by(Validation.at.desc()).limit(1)
        )
        closure_present = self.session.scalar(
            select(func.count()).select_from(ClosureRecord).where(ClosureRecord.case_id == case_id)
        ) or 0

        orientation = self.session.get(OrientationState, case_id)
        return DashboardSnapshot(
            case_id=case.case_id,
            case_code=case.case_code,
            case_status=case.status,
            current_phase=case.current_phase,
            phase_states=phase_states,
            open_flags=open_flags,
            active_tasks=active_tasks,
            submitted_tasks=submitted_tasks,
            document_summaries=tuple(summaries),
            other_documents_count=int(other_documents_count),
            last_validation_at=last_validation_at,
            closure_present=bool(closure_present),
            orientation_published=bool(orientation and orientation.published_version_id),
        )
