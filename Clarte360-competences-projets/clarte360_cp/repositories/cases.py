from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from clarte360_cp.domain.launch import LaunchContext
from .models import AuditEvent, Case, CaseContextRef, PhaseState


class ContextMismatchError(PermissionError):
    pass


class ConcurrentUpdateError(RuntimeError):
    pass


def _case_code(prescription_id: str) -> str:
    safe = prescription_id.replace(":", "-").replace(".", "-")
    return f"CP-{safe}"[:80]


class CaseRepository:
    def __init__(self, session: Session):
        self.session = session

    def open_or_create(self, ctx: LaunchContext) -> Case:
        ctx.require_scope("CP_CASE_OPEN")
        ref = self.session.scalar(select(CaseContextRef).where(CaseContextRef.prescription_id == ctx.prescription_id))
        if ref:
            if ref.beneficiary_id != ctx.beneficiary_id or ref.action_id != ctx.action_id:
                raise ContextMismatchError("Contexte bénéficiaire/action incohérent avec la prescription.")
            return self.session.get(Case, ref.case_id)  # type: ignore[return-value]

        case = Case(case_code=_case_code(ctx.prescription_id), status="INITIALISATION", current_phase=0)
        self.session.add(case)
        self.session.flush()
        self.session.add(CaseContextRef(
            case_id=case.case_id, beneficiary_id=ctx.beneficiary_id, action_id=ctx.action_id,
            prescription_id=ctx.prescription_id, participant_id=ctx.participant_id, hub_source=ctx.hub_source,
        ))
        for phase in range(12):
            self.session.add(PhaseState(case_id=case.case_id, phase_no=phase, state="DISPONIBLE" if phase == 0 else "NON_DISPONIBLE"))
        self.session.add(AuditEvent(
            case_id=case.case_id, event_type="CREATE", object_type="CASE", object_id=case.case_id,
            object_version=1, actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
        ))
        self.session.commit()
        return case

    def get(self, case_id: str) -> Case | None:
        return self.session.get(Case, case_id)

    def advance_current_phase(self, case_id: str, expected_row_version: int, new_phase: int) -> Case:
        case = self.session.get(Case, case_id)
        if not case:
            raise KeyError(case_id)
        if case.row_version != expected_row_version:
            raise ConcurrentUpdateError("Version serveur plus récente : recharge requise.")
        case.current_phase = new_phase
        try:
            self.session.commit()
        except StaleDataError as exc:
            self.session.rollback()
            raise ConcurrentUpdateError("Conflit de version.") from exc
        return case
