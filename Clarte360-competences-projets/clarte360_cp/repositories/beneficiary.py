from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    ActionItem,
    ActionPlan,
    Artifact,
    ArtifactVersion,
    CareerItem,
    ClosureRecord,
    ComparisonCell,
    ComparisonVersion,
    ExplorationIdea,
    IntersessionTask,
    JobTarget,
    MatchingItem,
    MatchingEvidence,
    PhaseState,
    ProjectDecision,
    PublicationEvent,
    ResultSet,
    ReviewFlag,
    SynthesisRecord,
    Validation,
    Case,
    OrientationState, OrientationVersion, OrientationFeedback,
)


@dataclass(frozen=True)
class BeneficiaryDocument:
    artifact_id: str
    artifact_type: str
    artifact_class: str
    version_no: int
    state: str
    published_at: object


@dataclass(frozen=True)
class BeneficiaryTask:
    task_id: str
    task_type: str
    state: str
    goal: str
    version_no: int
    job_label: str | None = None
    job_code: str | None = None


@dataclass(frozen=True)
class BeneficiaryMatchingDetail:
    job_code: str
    job_label: str
    item_label: str
    category: str
    status: str
    exercise_level: int | None
    evidence_titles: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class BeneficiaryCareerCard:
    item_type: str
    title: str
    organization: str | None
    start_date: str | None
    end_date: str | None
    details: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class BeneficiarySnapshot:
    case_id: str
    case_code: str
    case_status: str
    current_phase: int | None
    phase_states: tuple[tuple[int, str], ...]
    published_documents: tuple[BeneficiaryDocument, ...]
    tasks: tuple[BeneficiaryTask, ...]
    career_items: tuple[tuple[str, str, str | None], ...]
    ideas: tuple[tuple[str, str, str], ...]
    job_targets: tuple[tuple[str, str, str], ...]
    matching_counts: tuple[tuple[str, int], ...]
    comparison_cells: tuple[tuple[str, str, str], ...]
    project_decision: tuple[str, str] | None
    action_items: tuple[tuple[str, str | None, str | None], ...]
    result_state: str | None
    synthesis_state: str | None
    closure_present: bool
    last_validation_at: object | None
    orientation_published_version: int | None
    orientation_feedback: str | None
    matching_details: tuple[BeneficiaryMatchingDetail, ...] = ()
    project_alternative: tuple[str, str] | None = None
    career_details: tuple[BeneficiaryCareerCard, ...] = ()
    career_feedback: str | None = None
    career_feedback_comment: str | None = None
    career_feedback_version: int | None = None
    career_phase_version: int | None = None


class BeneficiaryRepository:
    """Projection lecture seule GO-21. Aucun brouillon documentaire interne n'est exposé."""

    VISIBLE_TASK_STATES = ("PUBLIEE", "EN_COURS", "SOUMISE", "A_DEBRIEFER", "CLOTUREE")

    def __init__(self, session: Session):
        self.session = session

    def load(self, case_id: str) -> BeneficiarySnapshot:
        case = self.session.get(Case, case_id)
        if case is None:
            raise KeyError(case_id)

        phase_states = tuple(
            (p.phase_no, p.state)
            for p in self.session.scalars(
                select(PhaseState).where(PhaseState.case_id == case_id).order_by(PhaseState.phase_no)
            )
        )

        published_rows = self.session.execute(
            select(Artifact, ArtifactVersion, PublicationEvent)
            .join(ArtifactVersion, PublicationEvent.artifact_version_id == ArtifactVersion.artifact_version_id)
            .join(Artifact, ArtifactVersion.artifact_id == Artifact.artifact_id)
            .where(
                PublicationEvent.case_id == case_id,
                PublicationEvent.audience == "BENEFICIAIRE",
                PublicationEvent.revoked_at.is_(None),
            )
            .order_by(PublicationEvent.published_at.desc())
        ).all()
        seen: set[str] = set()
        documents: list[BeneficiaryDocument] = []
        for artifact, version, event in published_rows:
            if artifact.artifact_id in seen:
                continue
            seen.add(artifact.artifact_id)
            documents.append(BeneficiaryDocument(
                artifact_id=artifact.artifact_id,
                artifact_type=artifact.artifact_type,
                artifact_class=artifact.artifact_class,
                version_no=version.version_no,
                state=version.state,
                published_at=event.published_at,
            ))

        task_rows = self.session.scalars(
            select(IntersessionTask)
            .where(
                IntersessionTask.case_id == case_id,
                IntersessionTask.state.in_(self.VISIBLE_TASK_STATES),
            )
            .order_by(IntersessionTask.created_at.desc())
        ).all()
        task_projection = []
        for task in task_rows:
            target = self.session.get(JobTarget, task.job_target_id) if task.job_target_id else None
            if target is not None and (target.case_id != case_id or target.status != "ACTIVE"):
                target = None
            task_projection.append(BeneficiaryTask(task.task_id, task.task_type, task.state,
                task.question_or_goal, task.version_no, target.rome_label if target else None,
                target.rome_code if target else None))
        tasks = tuple(task_projection)

        phase0_state = next((state for no, state in phase_states if no == 0), None)
        phase0 = self.session.scalar(select(PhaseState).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == 0,
        ))
        latest_career_feedback = self.session.scalar(select(Validation).where(
            Validation.case_id == case_id, Validation.object_type == "CAREER_PHASE0",
            Validation.object_id == "0",
        ).order_by(Validation.object_version.desc()).limit(1))
        career_feedback_comment = None
        if latest_career_feedback and latest_career_feedback.mode == "CORRECTION_DEMANDEE":
            flag = self.session.scalar(select(ReviewFlag).where(
                ReviewFlag.case_id == case_id, ReviewFlag.object_type == "CAREER_PHASE0",
                ReviewFlag.object_id == str(latest_career_feedback.object_version),
            ).order_by(ReviewFlag.flag_id.desc()).limit(1))
            career_feedback_comment = flag.reason if flag else None
        career_rows = self.session.scalars(
            select(CareerItem)
            .where(CareerItem.case_id == case_id, CareerItem.status == "ACTIVE")
            .order_by(CareerItem.start_date, CareerItem.title)
        ).all() if phase0_state in {"VALIDEE", "FIGEE_CLOTURE"} else []
        career_items = tuple((item.item_type, item.title, item.organization) for item in career_rows)
        career_details = []
        for item in career_rows:
            try:
                payload = json.loads(item.details_json or "{}")
            except (TypeError, ValueError):
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            detail_rows = tuple((label, str(payload.get(key, ""))) for key, label in (
                ("context", "Contexte / secteur"), ("activities", "Activités / contenus étudiés"),
                ("autonomie", "Responsabilités et autonomie"), ("realisations", "Réalisations / résultats"),
                ("outils", "Outils et méthodes"), ("savoirs", "Savoirs et savoir-faire"),
            ) if isinstance(payload.get(key), str) and payload.get(key).strip())
            level = payload.get("niveau_exercice")
            if level in {1, 2, 3}:
                detail_rows += (("Niveau discuté pour cette expérience", {
                    1: "1 — Pratique encadrée / contribution", 2: "2 — Maîtrise autonome",
                    3: "3 — Pilotage, expertise ou transmission",
                }[level]),)
            career_details.append(BeneficiaryCareerCard(item.item_type, item.title, item.organization,
                item.start_date, item.end_date, detail_rows))
        ideas = tuple(
            (idea.idea_id, idea.wording_current, idea.origin)
            for idea in self.session.scalars(
                select(ExplorationIdea)
                .where(ExplorationIdea.case_id == case_id, ExplorationIdea.status == "ACTIVE")
                .order_by(ExplorationIdea.wording_current)
            )
        )
        job_targets = tuple(
            (job.job_target_id, job.rome_label, job.rome_code)
            for job in self.session.scalars(
                select(JobTarget)
                .where(JobTarget.case_id == case_id, JobTarget.status == "ACTIVE")
                .order_by(JobTarget.selected_order, JobTarget.rome_label)
            )
        )

        counts = self.session.execute(
            select(MatchingItem.final_status, func.count())
            .where(MatchingItem.case_id == case_id, MatchingItem.review_required == 0)
            .group_by(MatchingItem.final_status)
        ).all()
        matching_counts = tuple(((status or "A_PRECISER"), int(count)) for status, count in counts)

        matching_details: list[BeneficiaryMatchingDetail] = []
        match_rows = self.session.scalars(select(MatchingItem).where(
            MatchingItem.case_id == case_id,
            MatchingItem.final_status.is_not(None),
            MatchingItem.review_required == 0,
        ).order_by(MatchingItem.category, MatchingItem.rome_label)).all()
        for match in match_rows:
            job = self.session.get(JobTarget, match.job_target_id)
            if job is None or job.status != "ACTIVE":
                continue
            evidence_rows = self.session.scalars(select(MatchingEvidence).where(
                MatchingEvidence.matching_id == match.matching_id,
            )).all()
            experience_titles = []
            rationales = []
            for evidence in evidence_rows:
                experience = self.session.get(CareerItem, evidence.source_id) if evidence.source_type == "CAREER_ITEM" else None
                if experience:
                    kind = {"EMPLOI": "Expérience", "ETUDE": "Études", "FORMATION": "Formation",
                            "AUTOFORMATION": "Apprentissage personnel", "AUTRE": "Autre parcours"}.get(experience.item_type, experience.item_type)
                    label = f"{kind} — {experience.title}"
                    if label not in experience_titles:
                        experience_titles.append(label)
                if evidence.rationale and evidence.rationale not in rationales:
                    rationales.append(evidence.rationale)
            matching_details.append(BeneficiaryMatchingDetail(
                job_code=job.rome_code, job_label=job.rome_label, item_label=match.rome_label,
                category=match.category, status=match.final_status, exercise_level=match.exercise_level,
                evidence_titles=tuple(experience_titles), rationale=" · ".join(rationales),
            ))

        comparison = self.session.scalar(
            select(ComparisonVersion)
            .where(ComparisonVersion.case_id == case_id, ComparisonVersion.state == "PUBLIEE")
            .order_by(ComparisonVersion.version_no.desc())
            .limit(1)
        )
        comparison_cells: tuple[tuple[str, str, str], ...] = ()
        # Une comparaison brouillon reste strictement interne; la dernière version publiée demeure lisible.
        if comparison is not None:
            comparison_cells = tuple(
                (cell.job_target_id, cell.criterion, cell.content)
                for cell in self.session.scalars(
                    select(ComparisonCell)
                    .where(ComparisonCell.comparison_id == comparison.comparison_id)
                    .order_by(ComparisonCell.criterion, ComparisonCell.job_target_id)
                )
            )

        decision = self.session.scalar(
            select(ProjectDecision)
            .join(Validation, (Validation.case_id == ProjectDecision.case_id) &
                  (Validation.object_id == ProjectDecision.decision_id) &
                  (Validation.object_type == "PROJECT_DECISION"))
            .where(ProjectDecision.case_id == case_id, ProjectDecision.decision_type == "PRIORITAIRE",
                   ProjectDecision.comparison_id == (comparison.comparison_id if comparison else ""))
            .order_by(ProjectDecision.beneficiary_decided_at.desc())
            .limit(1)
        )
        project_decision = None if decision is None else (decision.job_target_id, decision.beneficiary_wording)
        alternative = self.session.scalar(select(ProjectDecision).join(
            Validation, (Validation.case_id == ProjectDecision.case_id) &
            (Validation.object_id == ProjectDecision.decision_id) &
            (Validation.object_type == "PROJECT_DECISION")
        ).where(
            ProjectDecision.case_id == case_id, ProjectDecision.decision_type == "ALTERNATIVE",
            ProjectDecision.comparison_id == (comparison.comparison_id if comparison else ""),
        ).order_by(ProjectDecision.beneficiary_decided_at.desc()).limit(1))
        project_alternative = None if alternative is None else (alternative.job_target_id, alternative.beneficiary_wording)

        plan = self.session.scalar(
            select(ActionPlan)
            .where(ActionPlan.case_id == case_id, ActionPlan.state == "PUBLIEE")
            .order_by(ActionPlan.version_no.desc())
            .limit(1)
        )
        action_items: tuple[tuple[str, str | None, str | None], ...] = ()
        if plan is not None:
            action_items = tuple(
                (item.action_text, item.due_ref, item.expected_result)
                for item in self.session.scalars(
                    select(ActionItem)
                    .where(ActionItem.action_plan_id == plan.action_plan_id)
                    .order_by(ActionItem.action_text)
                )
            )

        result = self.session.scalar(
            select(ResultSet).where(ResultSet.case_id == case_id).order_by(ResultSet.version_no.desc()).limit(1)
        )
        synthesis = self.session.scalar(
            select(SynthesisRecord).where(SynthesisRecord.case_id == case_id).order_by(SynthesisRecord.version_no.desc()).limit(1)
        )
        closure_present = bool(self.session.scalar(
            select(func.count()).select_from(ClosureRecord).where(ClosureRecord.case_id == case_id)
        ) or 0)
        last_validation_at = self.session.scalar(
            select(Validation.at).where(Validation.case_id == case_id).order_by(Validation.at.desc()).limit(1)
        )

        o_state = self.session.get(OrientationState, case_id)
        o_version = self.session.get(OrientationVersion, o_state.published_version_id) if o_state and o_state.published_version_id else None
        o_feedback = self.session.scalar(select(OrientationFeedback).where(
            OrientationFeedback.orientation_version_id == o_version.orientation_version_id
        )) if o_version else None
        return BeneficiarySnapshot(
            case_id=case.case_id,
            case_code=case.case_code,
            case_status=case.status,
            current_phase=case.current_phase,
            phase_states=phase_states,
            published_documents=tuple(documents),
            tasks=tasks,
            career_items=career_items,
            ideas=ideas,
            job_targets=job_targets,
            matching_counts=matching_counts,
            comparison_cells=comparison_cells,
            project_decision=project_decision,
            action_items=action_items,
            result_state=None if result is None else result.state,
            synthesis_state=None if synthesis is None else synthesis.state,
            closure_present=closure_present,
            last_validation_at=last_validation_at,
            orientation_published_version=o_version.version_no if o_version else None,
            orientation_feedback=o_feedback.decision if o_feedback else None,
            matching_details=tuple(matching_details),
            project_alternative=project_alternative,
            career_details=tuple(career_details),
            career_feedback=latest_career_feedback.mode if latest_career_feedback else None,
            career_feedback_comment=career_feedback_comment,
            career_feedback_version=latest_career_feedback.object_version if latest_career_feedback else None,
            career_phase_version=phase0.current_version_no if phase0 else None,
        )
