"""Ciblage et retour des investigations réellement confiées entre deux séances."""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import func, select

from clarte360_cp.application.orientation import _context, OrientationAccessDenied
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import AuditEvent, IntersessionResponse, IntersessionTask, JobTarget


TASK_TYPES = {
    "ENQUETE_METIER": "Enquête métier",
    "OFFRES_EMPLOI": "Comparer des offres",
    "TERRITOIRE": "Vérifier le territoire",
    "CONDITION_ACCES": "Vérifier une condition d’accès",
    "FORMATION": "Rechercher une formation ou certification",
    "AUTRE": "Autre vérification utile",
}
VISIBLE_STATES = ("PUBLIEE", "EN_COURS", "SOUMISE", "A_DEBRIEFER", "CLOTUREE")


def _task_dict(task: IntersessionTask, response: IntersessionResponse | None,
               job_target: JobTarget | None = None) -> dict[str, Any]:
    return {
        "task_id": task.task_id, "task_type": task.task_type,
        "task_type_label": TASK_TYPES.get(task.task_type, "Investigation"),
        "job_target_id": task.job_target_id,
        "job_target_label": job_target.rome_label if job_target else None,
        "job_target_code": job_target.rome_code if job_target else None,
        "state": task.state, "goal": task.question_or_goal, "version_no": task.version_no,
        "response_id": response.response_id if response else None,
        "response": json.loads(response.response_json) if response else None,
    }


def read_intersession_tasks(ctx, case_id: str, *, database_url: str | None = None) -> tuple[dict[str, Any], ...]:
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        role = ctx.actor_role
        if role not in {ActorRole.ACCOMPAGNATEUR, ActorRole.BENEFICIAIRE}:
            raise OrientationAccessDenied("Action non autorisée pour ce rôle.")
        _context(session, ctx, case_id, role=role, scope="CP_CASE_READ")
        tasks = session.scalars(select(IntersessionTask).where(
            IntersessionTask.case_id == case_id, IntersessionTask.state.in_(VISIBLE_STATES),
        ).order_by(IntersessionTask.created_at.desc())).all()
        result = []
        for task in tasks:
            job_target = session.get(JobTarget, task.job_target_id) if task.job_target_id else None
            if job_target is not None and (job_target.case_id != case_id or job_target.status != "ACTIVE"):
                job_target = None
            response = session.scalar(select(IntersessionResponse).where(
                IntersessionResponse.case_id == case_id, IntersessionResponse.task_id == task.task_id,
            ).order_by(IntersessionResponse.version_no.desc()).limit(1))
            result.append(_task_dict(task, response, job_target))
        return tuple(result)


def create_intersession_task(ctx, case_id: str, *, task_type: str, goal: str,
                             job_target_id: str | None = None,
                             database_url: str | None = None) -> dict[str, Any]:
    task_type = str(task_type or "").strip().upper()
    normalized_goal = str(goal or "").strip()
    if task_type not in TASK_TYPES:
        raise ValueError("Choisissez une catégorie d’investigation reconnue.")
    if len(normalized_goal) < 12 or len(normalized_goal) > 2000:
        raise ValueError("Précisez une action utile en 12 à 2 000 caractères.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        job_target = None
        if job_target_id:
            job_target = session.get(JobTarget, str(job_target_id))
            if job_target is None or job_target.case_id != case_id or job_target.status != "ACTIVE":
                raise ValueError("Le métier ROME associé n’est plus actif dans ce dossier.")
        task = IntersessionTask(case_id=case_id, task_type=task_type, state="PUBLIEE",
            question_or_goal=normalized_goal, job_target_id=job_target.job_target_id if job_target else None,
            version_no=1, created_by=ctx.actor_id)
        session.add(task); session.flush()
        session.add(AuditEvent(case_id=case_id, event_type="INVESTIGATION_TASK_PUBLISHED",
            object_type="INTERSESSION_TASK", object_id=task.task_id, object_version=1,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"task_type": task_type, "goal_length": len(normalized_goal)})))
        session.commit()
        return _task_dict(task, None, job_target)


def submit_intersession_response(ctx, case_id: str, task_id: str, *, source: str,
                                 consulted_on: str, learned: str, project_impact: str,
                                 database_url: str | None = None) -> dict[str, Any]:
    fields = {"source": str(source or "").strip(), "learned": str(learned or "").strip(),
              "project_impact": str(project_impact or "").strip()}
    if any(not value for value in fields.values()):
        raise ValueError("Indiquez la source, ce que vous avez appris et l’effet sur votre projet.")
    if any(len(value) > 2400 for value in fields.values()):
        raise ValueError("Chaque réponse doit rester sous 2 400 caractères.")
    consulted_on = str(consulted_on or "").strip()
    try:
        consulted_on = date.fromisoformat(consulted_on).isoformat()
    except ValueError:
        raise ValueError("Indiquez une date de consultation au format AAAA-MM-JJ.") from None
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.BENEFICIAIRE, scope="CP_BENEFICIARY_INTERACT")
        task = session.get(IntersessionTask, task_id)
        if task is None or task.case_id != case_id or task.state not in {"PUBLIEE", "EN_COURS"}:
            raise OrientationAccessDenied("Cette action n’est plus ouverte à la transmission.")
        version = int(session.scalar(select(func.max(IntersessionResponse.version_no)).where(
            IntersessionResponse.case_id == case_id, IntersessionResponse.task_id == task_id)) or 0) + 1
        response = IntersessionResponse(case_id=case_id, task_id=task_id, version_no=version,
            response_json=json.dumps({**fields, "consulted_on": consulted_on, "response_state": "TRANSMISE"}, ensure_ascii=False, separators=(",", ":")),
            submitted_by=ctx.actor_id)
        session.add(response); session.flush()
        task.state = "SOUMISE"
        task.version_no += 1
        session.add(AuditEvent(case_id=case_id, event_type="INVESTIGATION_RESPONSE_SUBMITTED",
            object_type="INTERSESSION_TASK", object_id=task.task_id, object_version=task.version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"response_id": response.response_id, "response_version": version})))
        session.commit()
        return _task_dict(task, response)


def save_intersession_draft(ctx, case_id: str, task_id: str, *, source: str,
                            consulted_on: str, learned: str, project_impact: str,
                            database_url: str | None = None) -> dict[str, Any]:
    values = {"source": str(source or "").strip(), "consulted_on": str(consulted_on or "").strip(),
              "learned": str(learned or "").strip(), "project_impact": str(project_impact or "").strip()}
    if not any(values.values()):
        raise ValueError("Saisissez au moins un élément avant d’enregistrer le brouillon.")
    if any(len(value) > 2400 for value in values.values()):
        raise ValueError("Chaque réponse doit rester sous 2 400 caractères.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.BENEFICIAIRE, scope="CP_BENEFICIARY_INTERACT")
        task = session.get(IntersessionTask, task_id)
        if task is None or task.case_id != case_id or task.state not in {"PUBLIEE", "EN_COURS"}:
            raise OrientationAccessDenied("Cette action n’est plus ouverte à la sauvegarde.")
        version = int(session.scalar(select(func.max(IntersessionResponse.version_no)).where(
            IntersessionResponse.case_id == case_id, IntersessionResponse.task_id == task_id)) or 0) + 1
        response = IntersessionResponse(case_id=case_id, task_id=task_id, version_no=version,
            response_json=json.dumps({**values, "response_state": "BROUILLON"}, ensure_ascii=False, separators=(",", ":")),
            submitted_by=ctx.actor_id)
        session.add(response); session.flush()
        task.state = "EN_COURS"; task.version_no += 1
        session.add(AuditEvent(case_id=case_id, event_type="INVESTIGATION_RESPONSE_DRAFT_SAVED",
            object_type="INTERSESSION_TASK", object_id=task.task_id, object_version=task.version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"response_id": response.response_id, "response_version": version})))
        session.commit()
        return _task_dict(task, response)


def close_intersession_task(ctx, case_id: str, task_id: str, *, database_url: str | None = None) -> None:
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        task = session.get(IntersessionTask, task_id)
        if task is None or task.case_id != case_id or task.state not in {"SOUMISE", "A_DEBRIEFER"}:
            raise OrientationAccessDenied("Aucun retour soumis n’est disponible pour ce débrief.")
        task.state = "CLOTUREE"; task.version_no += 1
        session.add(AuditEvent(case_id=case_id, event_type="INVESTIGATION_TASK_DEBRIEFED",
            object_type="INTERSESSION_TASK", object_id=task.task_id, object_version=task.version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"task_type": task.task_type})))
        session.commit()
