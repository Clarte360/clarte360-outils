"""Beneficiary response to the shared career journey (GO22 phase 0)."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import (
    AuditEvent, CareerItem, Case, PhaseEvent, PhaseState, ReviewFlag, Validation,
)
from .orientation import _context


class CareerFeedbackConflict(RuntimeError):
    """The shared career version changed or already received a response."""


def read_career_phase_feedback(ctx, case_id: str, *, database_url: str | None = None) -> dict | None:
    """Return the current beneficiary response for the accompanist's review."""
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_READ")
        state = session.scalar(select(PhaseState).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == 0,
        ))
        if state is None:
            return None
        response = session.scalar(select(Validation).where(
            Validation.case_id == case_id, Validation.object_type == "CAREER_PHASE0",
            Validation.object_id == "0",
        ).order_by(Validation.object_version.desc()).limit(1))
        if response is None:
            return None
        current = (
            response.mode == "CONFIRME" and state.current_version_no == response.object_version
        ) or (
            response.mode == "CORRECTION_DEMANDEE" and state.current_version_no == response.object_version + 1
        )
        if not current:
            return None
        flag = session.scalar(select(ReviewFlag).where(
            ReviewFlag.case_id == case_id, ReviewFlag.object_type == "CAREER_PHASE0",
            ReviewFlag.object_id == str(response.object_version),
        ).order_by(ReviewFlag.flag_id.desc()).limit(1)) if response.mode == "CORRECTION_DEMANDEE" else None
        return {"decision": response.mode, "comment": flag.reason if flag else None,
                "version": response.object_version}


def respond_to_career_phase(ctx, case_id: str, *, version: int, decision: str,
                            comment: str = "", database_url: str | None = None) -> None:
    if decision not in {"CONFIRME", "CORRECTION_DEMANDEE"}:
        raise ValueError("Choisissez une confirmation ou une demande de correction.")
    clean = str(comment or "").strip()
    if len(clean) > 1000:
        raise ValueError("Le commentaire doit rester sous 1 000 caractères.")
    if decision == "CORRECTION_DEMANDEE" and len(clean) < 4:
        raise ValueError("Décrivez en quelques mots la correction attendue.")

    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.BENEFICIAIRE,
                 scope="CP_BENEFICIARY_VALIDATE")
        state = session.scalar(select(PhaseState).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == 0,
        ))
        case = session.get(Case, case_id)
        if state is None or case is None or state.state != "VALIDEE":
            raise CareerFeedbackConflict("Le parcours partagé a changé. Rechargez votre espace.")
        if state.current_version_no != int(version):
            raise CareerFeedbackConflict("La version partagée a changé. Rechargez avant de répondre.")
        already_answered = session.scalar(select(Validation).where(
            Validation.case_id == case_id, Validation.object_type == "CAREER_PHASE0",
            Validation.object_id == "0", Validation.object_version == int(version),
        ))
        if already_answered:
            raise CareerFeedbackConflict("Une réponse a déjà été enregistrée pour cette version.")

        session.add(Validation(
            event_key=f"CAREER_PHASE0:{version}:{decision}", case_id=case_id, phase_no=0,
            object_type="CAREER_PHASE0", object_id="0", object_version=int(version),
            actor_type=ActorRole.BENEFICIAIRE.value, actor_id=ctx.actor_id, mode=decision,
        ))
        if decision == "CORRECTION_DEMANDEE":
            session.add(ReviewFlag(case_id=case_id, object_type="CAREER_PHASE0",
                object_id=str(version), reason=clean, impact_level="NORMAL", status="OPEN"))
            old_state = state.state
            state.state = "REOUVERTE"
            state.current_version_no += 1
            session.add(PhaseEvent(case_id=case_id, phase_no=0, from_state=old_state,
                to_state="REOUVERTE", actor_type=ActorRole.BENEFICIAIRE.value,
                actor_id=ctx.actor_id, reason="Le bénéficiaire demande une correction du parcours partagé."))
            case.current_phase = 0
            case.status = "EN_COURS"
            for item in session.scalars(select(CareerItem).where(
                CareerItem.case_id == case_id, CareerItem.status == "ACTIVE",
            )):
                try:
                    details = json.loads(item.details_json or "{}")
                except (TypeError, json.JSONDecodeError):
                    details = {}
                if isinstance(details, dict):
                    details["statut_humain"] = "A_CONFIRMER"
                    item.details_json = json.dumps(details, ensure_ascii=False, separators=(",", ":"))

        session.add(AuditEvent(case_id=case_id, event_type="CAREER_PHASE0_FEEDBACK",
            object_type="CAREER_PHASE0", object_id="0", object_version=int(version),
            actor_type=ActorRole.BENEFICIAIRE.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"decision": decision, "comment_length": len(clean)})))
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise CareerFeedbackConflict("Une réponse a été enregistrée entre-temps. Actualisez votre espace.") from exc
