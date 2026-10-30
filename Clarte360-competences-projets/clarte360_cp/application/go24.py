"""GO24 — plan d'action versionné et retour explicite du bénéficiaire."""
from __future__ import annotations

import json
from sqlalchemy import func, select

from clarte360_cp.application.orientation import _context, OrientationAccessDenied
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import (
    ActionItem, ActionPlan, AuditEvent, ComparisonVersion, ProjectDecision, ReviewFlag, Validation,
)


def read_action_plan(ctx, case_id: str, *, database_url: str | None = None) -> dict:
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ctx.actor_role, scope="CP_CASE_READ")
        current_comparison = session.scalar(select(ComparisonVersion).where(
            ComparisonVersion.case_id == case_id, ComparisonVersion.state == "PUBLIEE",
        ).order_by(ComparisonVersion.version_no.desc()).limit(1))
        query = select(ActionPlan).where(ActionPlan.case_id == case_id)
        if ctx.actor_role is ActorRole.BENEFICIAIRE:
            if current_comparison is None:
                query = query.where(False)
            else:
                current_decision_ids = select(ProjectDecision.decision_id).where(
                    ProjectDecision.case_id == case_id,
                    ProjectDecision.decision_type == "PRIORITAIRE",
                    ProjectDecision.comparison_id == current_comparison.comparison_id,
                )
                query = query.where(ActionPlan.state == "PUBLIEE", ActionPlan.decision_id.in_(current_decision_ids))
        plan = session.scalar(query.order_by(ActionPlan.version_no.desc()).limit(1))
        if plan is None:
            outdated = bool(session.scalar(select(ActionPlan.action_plan_id).join(
                ProjectDecision, ProjectDecision.decision_id == ActionPlan.decision_id,
            ).where(
                ActionPlan.case_id == case_id, ActionPlan.state == "PUBLIEE",
                ProjectDecision.comparison_id != (current_comparison.comparison_id if current_comparison else ""),
            ).limit(1)))
            return {"plan_id": None, "version_no": None, "state": None, "items": (), "decision": None,
                    "beneficiary_response": None, "is_current": False, "out_of_date": outdated}
        items = tuple({"action": item.action_text, "due": item.due_ref, "means": item.means_text,
                       "expected": item.expected_result}
                      for item in session.scalars(select(ActionItem).where(
                          ActionItem.action_plan_id == plan.action_plan_id).order_by(ActionItem.action_item_id)))
        decision = session.get(ProjectDecision, plan.decision_id)
        plan_is_current = bool(current_comparison and decision and decision.comparison_id == current_comparison.comparison_id)
        response = session.scalar(select(Validation).where(
            Validation.case_id == case_id, Validation.object_type == "ACTION_PLAN",
            Validation.object_id == plan.action_plan_id,
        ).order_by(Validation.at.desc()).limit(1))
        return {"plan_id": plan.action_plan_id, "version_no": plan.version_no, "state": plan.state,
                "items": items, "decision": (decision.decision_type, decision.beneficiary_wording) if decision else None,
                "beneficiary_response": response.mode if response else None, "is_current": plan_is_current,
                "out_of_date": not plan_is_current}


def save_action_plan(ctx, case_id: str, items: list[dict], *, publish: bool = False,
                     database_url: str | None = None) -> int:
    clean = []
    for row in items:
        action = str(row.get("action", "") or "").strip()
        due = str(row.get("due", "") or "").strip()
        means = str(row.get("means", "") or "").strip()
        expected = str(row.get("expected", "") or "").strip()
        if not any((action, due, means, expected)):
            continue
        if len(action) < 8:
            raise ValueError("Chaque action doit décrire une étape concrète en au moins 8 caractères.")
        if any(len(value) > 2400 for value in (action, due, means, expected)):
            raise ValueError("Une rubrique dépasse la longueur maximale de 2 400 caractères.")
        clean.append((action, due or None, means or None, expected or None))
    if not 1 <= len(clean) <= 12:
        raise ValueError("Le plan doit contenir entre 1 et 12 actions concrètes.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        decision = session.scalar(select(ProjectDecision).where(
            ProjectDecision.case_id == case_id, ProjectDecision.decision_type == "PRIORITAIRE",
        ).order_by(ProjectDecision.beneficiary_decided_at.desc()).limit(1))
        if decision is None:
            raise ValueError("Formalisez le projet prioritaire avec le bénéficiaire en phase 7 avant le plan d'action.")
        comparison = session.scalar(select(ComparisonVersion).where(
            ComparisonVersion.case_id == case_id, ComparisonVersion.state == "PUBLIEE",
        ).order_by(ComparisonVersion.version_no.desc()).limit(1))
        if comparison is None or decision.comparison_id != comparison.comparison_id:
            raise ValueError("La comparaison a changé. Reconfirmez avec le bénéficiaire le projet prioritaire avant le plan d'action.")
        if not session.scalar(select(Validation.validation_id).where(
            Validation.case_id == case_id, Validation.object_type == "PROJECT_DECISION",
            Validation.object_id == decision.decision_id,
        )):
            raise ValueError("Partagez d'abord avec le bénéficiaire le projet prioritaire validé en séance.")
        latest = int(session.scalar(select(func.max(ActionPlan.version_no)).where(
            ActionPlan.case_id == case_id)) or 0)
        plan = ActionPlan(case_id=case_id, decision_id=decision.decision_id,
                          version_no=latest + 1, state="PUBLIEE" if publish else "BROUILLON")
        session.add(plan); session.flush()
        for action, due, means, expected in clean:
            session.add(ActionItem(case_id=case_id, action_plan_id=plan.action_plan_id,
                action_text=action, due_ref=due, means_text=means, expected_result=expected))
        session.add(AuditEvent(case_id=case_id,
            event_type="ACTION_PLAN_PUBLISHED" if publish else "ACTION_PLAN_SAVED",
            object_type="ACTION_PLAN", object_id=plan.action_plan_id,
            object_version=plan.version_no, actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"item_count": len(clean)})))
        session.commit()
        return plan.version_no


def respond_to_action_plan(ctx, case_id: str, *, plan_id: str, response: str, comment: str = "",
                           database_url: str | None = None) -> None:
    response = str(response or "").strip().upper()
    comment = str(comment or "").strip()
    if response not in {"CONFIRME", "AJUSTEMENT_DEMANDE"}:
        raise ValueError("Choisissez une réponse proposée.")
    if response == "AJUSTEMENT_DEMANDE" and len(comment) < 4:
        raise ValueError("Précisez le point du plan à ajuster.")
    if len(comment) > 2000:
        raise ValueError("Le commentaire dépasse 2 000 caractères.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.BENEFICIAIRE, scope="CP_BENEFICIARY_VALIDATE")
        plan = session.get(ActionPlan, plan_id)
        if plan is None or plan.case_id != case_id or plan.state != "PUBLIEE":
            raise OrientationAccessDenied("Ce plan n'est pas partagé avec ce bénéficiaire.")
        prior = session.scalar(select(Validation).where(
            Validation.case_id == case_id, Validation.object_type == "ACTION_PLAN",
            Validation.object_id == plan_id,
        ).limit(1))
        if prior:
            raise ValueError("Une réponse a déjà été donnée pour cette version du plan.")
        mode = "EXPLICITE" if response == "CONFIRME" else "AJUSTEMENT_DEMANDE"
        validation = Validation(event_key=f"ACTION_PLAN:{plan_id}:{response}", case_id=case_id,
            phase_no=8, object_type="ACTION_PLAN", object_id=plan_id, object_version=plan.version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id, mode=mode)
        session.add(validation)
        if response == "AJUSTEMENT_DEMANDE":
            session.add(ReviewFlag(case_id=case_id, object_type="ACTION_PLAN", object_id=plan_id,
                reason=comment, impact_level="NORMAL", status="OPEN"))
        session.add(AuditEvent(case_id=case_id, event_type="ACTION_PLAN_BENEFICIARY_RESPONSE",
            object_type="ACTION_PLAN", object_id=plan_id, object_version=plan.version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"response": response})))
        session.commit()
