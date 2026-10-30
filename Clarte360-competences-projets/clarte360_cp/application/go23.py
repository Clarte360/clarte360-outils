"""GO23 — comparaison qualitative et décision de projet, validées par l'humain."""
from __future__ import annotations

import json
from sqlalchemy import func, select

from clarte360_cp.application.orientation import _context, OrientationAccessDenied
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import (
    AuditEvent, Case, ComparisonCell, ComparisonVersion, JobTarget, PhaseEvent, PhaseState,
    ProjectDecision, Validation,
)

CRITERIA = (
    "Savoirs et compétences mobilisables",
    "Diplôme ou titre officiellement obligatoire",
    "Autres conditions d'accès",
    "Conditions d'exercice",
    "Marché du travail",
    "Contraintes et points à vérifier",
)
DECISION_TYPES = {"PRIORITAIRE", "ALTERNATIVE"}


def _reopen_comparison_dependents(session, case_id: str, ctx) -> None:
    """A newly shared comparison reopens its decision and conclusion steps."""
    changed = False
    for phase_no in range(6, 12):
        state = session.scalar(select(PhaseState).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == phase_no,
        ))
        if state is None or state.state not in {"VALIDEE", "FIGEE_CLOTURE"}:
            continue
        old_state = state.state
        state.state = "REOUVERTE"
        state.current_version_no += 1
        session.add(PhaseEvent(case_id=case_id, phase_no=phase_no,
            from_state=old_state, to_state="REOUVERTE", actor_type=ctx.actor_role.value,
            actor_id=ctx.actor_id,
            reason="Une nouvelle comparaison publiée demande de reprendre la décision et les livrables qui en dépendent."))
        changed = True
    if changed:
        case = session.get(Case, case_id)
        if case is not None:
            case.current_phase = 6
            case.status = "EN_COURS"


def _targets(session, case_id: str):
    return session.scalars(select(JobTarget).where(
        JobTarget.case_id == case_id, JobTarget.status == "ACTIVE",
    ).order_by(JobTarget.selected_order, JobTarget.rome_code)).all()


def read_go23(ctx, case_id: str, *, database_url: str | None = None) -> dict:
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ctx.actor_role, scope="CP_CASE_READ")
        targets = _targets(session, case_id)
        published_comparison = session.scalar(select(ComparisonVersion).where(
            ComparisonVersion.case_id == case_id, ComparisonVersion.state == "PUBLIEE",
        ).order_by(ComparisonVersion.version_no.desc()).limit(1))
        version = session.scalar(select(ComparisonVersion).where(
            ComparisonVersion.case_id == case_id,
            *([ComparisonVersion.state == "PUBLIEE"] if ctx.actor_role is ActorRole.BENEFICIAIRE else []),
        ).order_by(ComparisonVersion.version_no.desc()).limit(1))
        cells = ()
        if version:
            cells = tuple((cell.job_target_id, cell.criterion, cell.content)
                for cell in session.scalars(select(ComparisonCell).where(
                    ComparisonCell.comparison_id == version.comparison_id,
                ).order_by(ComparisonCell.criterion, ComparisonCell.job_target_id)))
        decisions = {}
        decision_ids = {}
        decision_published = {}
        for decision_type in DECISION_TYPES:
            if ctx.actor_role is ActorRole.BENEFICIAIRE:
                # A recorded session note is not visible to the beneficiary until
                # its accompanist explicitly publishes it through a validation.
                decision_query = select(ProjectDecision).where(
                    ProjectDecision.case_id == case_id,
                    ProjectDecision.decision_type == decision_type,
                    ProjectDecision.comparison_id == (published_comparison.comparison_id if published_comparison else ""),
                    select(1).where(
                        Validation.case_id == case_id,
                        Validation.object_type == "PROJECT_DECISION",
                        Validation.object_id == ProjectDecision.decision_id,
                    ).correlate(ProjectDecision).exists(),
                )
            else:
                decision_query = select(ProjectDecision).where(
                    ProjectDecision.case_id == case_id,
                    ProjectDecision.decision_type == decision_type,
                    ProjectDecision.comparison_id == (published_comparison.comparison_id if published_comparison else ""),
                )
            latest = session.scalar(decision_query.order_by(ProjectDecision.beneficiary_decided_at.desc()).limit(1))
            if latest:
                decisions[decision_type] = (latest.job_target_id, latest.beneficiary_wording)
                decision_ids[decision_type] = latest.decision_id
                decision_published[decision_type] = bool(session.scalar(select(Validation.validation_id).where(
                    Validation.case_id == case_id, Validation.object_type == "PROJECT_DECISION",
                    Validation.object_id == latest.decision_id,
                )))
        stale_types = set(session.scalars(select(ProjectDecision.decision_type).where(
            ProjectDecision.case_id == case_id,
            ProjectDecision.decision_type.in_(DECISION_TYPES),
            ProjectDecision.comparison_id != (published_comparison.comparison_id if published_comparison else ""),
        ).distinct()))
        return {
            "targets": tuple((job.job_target_id, job.rome_label, job.rome_code) for job in targets),
            "comparison_version": version.version_no if version else None,
            "comparison_state": version.state if version else None,
            "comparison_cells": cells,
            "decisions": decisions,
            "decision_ids": decision_ids,
            "decision_published": decision_published,
            "decision_out_of_date": any(kind not in decisions for kind in stale_types),
        }


def save_comparison(ctx, case_id: str, cells: list[dict], *, publish: bool = False,
                    database_url: str | None = None) -> int:
    """Crée une version de comparaison. Les cellules ne contiennent aucun score."""
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        targets = {job.job_target_id for job in _targets(session, case_id)}
        if not targets:
            raise ValueError("Ajoutez au moins un métier ROME actif avant de comparer les projets.")
        clean = []
        seen = set()
        for cell in cells:
            target = str(cell.get("job_target_id", ""))
            criterion = str(cell.get("criterion", ""))
            content = str(cell.get("content", "") or "").strip()
            if target not in targets or criterion not in CRITERIA:
                raise ValueError("La comparaison contient un métier ou un critère non reconnu.")
            key = (target, criterion)
            if key in seen:
                raise ValueError("Une seule observation est attendue par métier et par critère.")
            seen.add(key)
            if len(content) > 2400:
                raise ValueError("Chaque observation doit rester sous 2 400 caractères.")
            if content:
                clean.append((target, criterion, content))
        if not clean:
            raise ValueError("Renseignez au moins une observation qualitative avant d'enregistrer.")
        expected = {(target, criterion) for target in targets for criterion in CRITERIA}
        missing = expected - seen
        if publish and missing:
            raise ValueError(
                "La comparaison n'est pas complète. Pour chaque métier et chaque critère, indiquez un constat "
                "ou écrivez explicitement « À vérifier » avant de l'enregistrer."
            )
        if publish and len(clean) != len(expected):
            raise ValueError(
                "Pour partager la comparaison, renseignez chaque critère pour chaque métier. "
                "Quand une information manque, inscrivez « À vérifier » et précisez la démarche utile."
            )
        latest_no = int(session.scalar(select(func.max(ComparisonVersion.version_no)).where(
            ComparisonVersion.case_id == case_id)) or 0)
        version = ComparisonVersion(case_id=case_id, version_no=latest_no + 1,
                                    state="PUBLIEE" if publish else "BROUILLON")
        session.add(version); session.flush()
        for target, criterion, content in clean:
            session.add(ComparisonCell(case_id=case_id, comparison_id=version.comparison_id,
                job_target_id=target, criterion=criterion, content=content))
        if publish:
            _reopen_comparison_dependents(session, case_id, ctx)
        session.add(AuditEvent(case_id=case_id,
            event_type="PROJECT_COMPARISON_PUBLISHED" if publish else "PROJECT_COMPARISON_SAVED",
            object_type="COMPARISON", object_id=version.comparison_id,
            object_version=version.version_no, actor_type=ctx.actor_role.value,
            actor_id=ctx.actor_id, metadata_json_minimized=json.dumps({"cell_count": len(clean)})))
        session.commit()
        return version.version_no


def publish_comparison(ctx, case_id: str, *, database_url: str | None = None) -> int:
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_PUBLISH")
        version = session.scalar(select(ComparisonVersion).where(
            ComparisonVersion.case_id == case_id,
        ).order_by(ComparisonVersion.version_no.desc()).limit(1))
        if version is None:
            raise ValueError("Enregistrez une comparaison avant de la partager.")
        targets = {job.job_target_id for job in _targets(session, case_id)}
        actual = {(cell.job_target_id, cell.criterion) for cell in session.scalars(select(ComparisonCell).where(
            ComparisonCell.comparison_id == version.comparison_id,
        ))}
        expected = {(target, criterion) for target in targets for criterion in CRITERIA}
        if actual != expected:
            raise ValueError("Complétez chaque critère pour chaque métier (un constat ou « À vérifier ») avant de partager.")
        if version.state == "PUBLIEE":
            raise ValueError("La dernière comparaison est déjà partagée.")
        version.state = "PUBLIEE"
        _reopen_comparison_dependents(session, case_id, ctx)
        session.add(AuditEvent(case_id=case_id, event_type="PROJECT_COMPARISON_PUBLISHED",
            object_type="COMPARISON", object_id=version.comparison_id,
            object_version=version.version_no, actor_type=ctx.actor_role.value,
            actor_id=ctx.actor_id, metadata_json_minimized="{}"))
        session.commit()
        return version.version_no


def record_project_decision(ctx, case_id: str, *, job_target_id: str, decision_type: str,
                            wording: str, database_url: str | None = None) -> str:
    decision_type = str(decision_type or "").strip().upper()
    wording = str(wording or "").strip()
    if decision_type not in DECISION_TYPES:
        raise ValueError("Choisissez un projet prioritaire ou une alternative.")
    if not 12 <= len(wording) <= 2000:
        raise ValueError("Notez les raisons exprimées par le bénéficiaire en 12 à 2 000 caractères.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        comparison = session.scalar(select(ComparisonVersion).where(
            ComparisonVersion.case_id == case_id, ComparisonVersion.state == "PUBLIEE",
        ).order_by(ComparisonVersion.version_no.desc()).limit(1))
        if comparison is None:
            raise ValueError("Partagez d'abord une comparaison complète avec le bénéficiaire avant de formaliser son choix.")
        target = session.get(JobTarget, job_target_id)
        if target is None or target.case_id != case_id or target.status != "ACTIVE":
            raise OrientationAccessDenied("Ce métier n'appartient pas aux pistes actives de ce dossier.")
        counterpart = "ALTERNATIVE" if decision_type == "PRIORITAIRE" else "PRIORITAIRE"
        other = session.scalar(select(ProjectDecision).where(
            ProjectDecision.case_id == case_id, ProjectDecision.decision_type == counterpart,
            ProjectDecision.comparison_id == comparison.comparison_id,
        ).order_by(ProjectDecision.beneficiary_decided_at.desc()).limit(1))
        if other is not None and other.job_target_id == job_target_id:
            raise ValueError("Le projet prioritaire et l'alternative doivent désigner deux métiers différents.")
        decision = ProjectDecision(case_id=case_id, job_target_id=job_target_id,
            comparison_id=comparison.comparison_id, decision_type=decision_type,
            beneficiary_wording=wording)
        session.add(decision); session.flush()
        session.add(AuditEvent(case_id=case_id, event_type="BENEFICIARY_PROJECT_DECISION_RECORDED",
            object_type="PROJECT_DECISION", object_id=decision.decision_id,
            object_version=1, actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"decision_type": decision_type})))
        session.commit()
        return decision.decision_id


def publish_project_decision(ctx, case_id: str, *, decision_id: str,
                             database_url: str | None = None) -> None:
    """Explicitly publish the session-recorded beneficiary choice."""
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_PUBLISH")
        decision = session.get(ProjectDecision, decision_id)
        if decision is None or decision.case_id != case_id:
            raise OrientationAccessDenied("Cette décision n'appartient pas au dossier courant.")
        comparison = session.scalar(select(ComparisonVersion).where(
            ComparisonVersion.case_id == case_id, ComparisonVersion.state == "PUBLIEE",
        ).order_by(ComparisonVersion.version_no.desc()).limit(1))
        if comparison is None or decision.comparison_id != comparison.comparison_id:
            raise ValueError("La comparaison a changé. Reprenez le choix en séance avant de le partager.")
        if session.scalar(select(Validation.validation_id).where(
            Validation.case_id == case_id, Validation.object_type == "PROJECT_DECISION",
            Validation.object_id == decision_id,
        )):
            raise ValueError("Cette décision est déjà partagée avec le bénéficiaire.")
        session.add(Validation(
            event_key=f"PROJECT_DECISION:{decision_id}:PUBLISHED", case_id=case_id,
            phase_no=7, object_type="PROJECT_DECISION", object_id=decision_id,
            object_version=1, actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            mode="PUBLICATION_EXPLICITE",
        ))
        session.add(AuditEvent(case_id=case_id, event_type="PROJECT_DECISION_PUBLISHED",
            object_type="PROJECT_DECISION", object_id=decision_id, object_version=1,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"decision_type": decision.decision_type})))
        session.commit()
