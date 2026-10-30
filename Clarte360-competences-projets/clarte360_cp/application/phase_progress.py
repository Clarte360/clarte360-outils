"""Explicit phase readiness and human validation for GO22–GO24."""
from __future__ import annotations

import json

from sqlalchemy import func, select

from clarte360_cp.application.go23 import CRITERIA
from clarte360_cp.application.orientation import _context
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.domain.phases import PHASE_NEXT, PHASE_PREVIOUS
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import (
    ActionPlan, ActionItem, Artifact, ArtifactVersion, AuditEvent, CareerItem,
    CareerVersion, Case, Cav3Analysis, ClarificationItem, ClosureRecord,
    ComparisonCell, ComparisonVersion, ExplorationIdea, ExternalSnapshot,
    FollowUpPlan, IntersessionTask, JobTarget, MatchingItem, PhaseEvent,
    PhaseState, PreparationState, PreparationResponse, ProjectDecision,
    ResultSet, ReviewFlag, RomeMatchingReview, SynthesisRecord, Validation,
)


PHASE_LABELS = {
    0: "Parcours professionnel enrichi", 1: "Pistes professionnelles", 2: "Métiers ROME retenus",
    3: "Rapprochement des savoirs", 4: "Incertitudes et points à préciser",
    5: "Investigations terrain et marché", 6: "Comparaison des pistes", 7: "Projet retenu et sécurisation",
    8: "Plan d'action", 9: "Résultats détaillés", 10: "Synthèse finale", 11: "Clôture et suivi",
}


def _exists(session, model, *criteria) -> bool:
    return bool(session.scalar(select(func.count()).select_from(model).where(*criteria)) or 0)


def phase_readiness(ctx, case_id: str, phase_no: int, *, database_url: str | None = None) -> tuple[str, ...]:
    """Return unmet evidence/decision conditions for one phase."""
    if not 0 <= int(phase_no) <= 11:
        raise ValueError("Numéro de phase non reconnu.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_READ")
        missing: list[str] = []
        targets = session.scalars(select(JobTarget).where(JobTarget.case_id == case_id,
            JobTarget.status == "ACTIVE").order_by(JobTarget.selected_order)).all()
        if phase_no == 0:
            career_rows = session.scalars(select(CareerItem).where(
                CareerItem.case_id == case_id, CareerItem.status == "ACTIVE")).all()
            if not career_rows:
                missing.append("Le parcours enrichi doit contenir au moins une expérience, étude, formation ou autoformation.")
            else:
                unreviewed = []
                for item in career_rows:
                    try:
                        details = json.loads(item.details_json or "{}")
                    except (TypeError, json.JSONDecodeError):
                        details = {}
                    if not isinstance(details, dict) or details.get("statut_humain") != "RELUE_EN_SEANCE":
                        unreviewed.append(item.title)
                if unreviewed:
                    titles = ", ".join(unreviewed[:5])
                    missing.append("Relisez chaque carte avec le bénéficiaire avant de partager le parcours : " + titles + ("…" if len(unreviewed) > 5 else "."))
        elif phase_no == 1:
            if not _exists(session, ExplorationIdea, ExplorationIdea.case_id == case_id, ExplorationIdea.status == "ACTIVE"):
                missing.append("Consignez une piste exprimée ou un constat explicite qu'aucune piste n'est encore identifiée.")
        elif phase_no == 2:
            if not targets:
                missing.append("Retenez au moins un métier ROME, ou consignez qu'aucun métier n'est retenu à ce stade.")
            for target in targets:
                if not target.snapshot_id or session.get(ExternalSnapshot, target.snapshot_id) is None:
                    missing.append(f"La fiche ROME {target.rome_code} doit avoir une source datée enregistrée.")
                if target.beneficiary_confirmed_at is None:
                    missing.append(f"La sélection du métier {target.rome_code} doit être confirmée par le bénéficiaire.")
        elif phase_no == 3:
            if not targets:
                missing.append("Aucun métier retenu : consignez la raison et la prochaine investigation avant de valider.")
            for target in targets:
                review = session.scalar(select(RomeMatchingReview).where(
                    RomeMatchingReview.case_id == case_id, RomeMatchingReview.job_target_id == target.job_target_id,
                ).order_by(RomeMatchingReview.version_no.desc()).limit(1))
                if review is None:
                    missing.append(f"La revue humaine des savoirs ROME {target.rome_code} manque.")
                elif _exists(session, MatchingItem, MatchingItem.case_id == case_id,
                             MatchingItem.job_target_id == target.job_target_id,
                             MatchingItem.review_required == 1):
                    missing.append(f"Des savoirs de {target.rome_code} restent à confirmer après la dernière modification du parcours.")
        elif phase_no == 4:
            if _exists(session, ClarificationItem, ClarificationItem.case_id == case_id, ClarificationItem.status == "OPEN"):
                missing.append("Il reste des questions de clarification ouvertes.")
            if _exists(session, ReviewFlag, ReviewFlag.case_id == case_id, ReviewFlag.status == "OPEN"):
                missing.append("Il reste des points signalés à traiter avant la suite.")
            prep = session.get(PreparationState, case_id)
            if prep is not None and prep.active_response_id and prep.reviewed_response_id:
                if not _exists(session, Cav3Analysis, Cav3Analysis.case_id == case_id,
                               Cav3Analysis.response_id == prep.reviewed_response_id):
                    missing.append("L'analyse C-AV3 attendue à partir de la réponse reprise en séance n'est pas enregistrée.")
        elif phase_no == 5:
            if _exists(session, IntersessionTask, IntersessionTask.case_id == case_id,
                       IntersessionTask.state.in_(["PUBLIEE", "EN_COURS", "SOUMISE", "A_DEBRIEFER"])):
                missing.append("Chaque investigation confiée doit avoir été débriefée et clôturée.")
            for target in targets:
                completed = _exists(session, IntersessionTask,
                    IntersessionTask.case_id == case_id,
                    IntersessionTask.job_target_id == target.job_target_id,
                    IntersessionTask.state == "CLOTUREE")
                if not completed:
                    missing.append(
                        f"Le métier {target.rome_code} doit avoir au moins une investigation confiée au bénéficiaire, "
                        "son retour reçu et son débrief réalisé avant de comparer les projets."
                    )
        elif phase_no == 6:
            comparison = session.scalar(select(ComparisonVersion).where(
                ComparisonVersion.case_id == case_id, ComparisonVersion.state == "PUBLIEE",
            ).order_by(ComparisonVersion.version_no.desc()).limit(1))
            if comparison is None:
                missing.append("Partagez une comparaison avant de valider cette phase.")
            else:
                expected = {(t.job_target_id, c) for t in targets for c in CRITERIA}
                actual = {(x.job_target_id, x.criterion) for x in session.scalars(select(ComparisonCell).where(
                    ComparisonCell.comparison_id == comparison.comparison_id))}
                if not expected or actual != expected:
                    missing.append("Chaque métier doit être comparé selon chacun des critères, y compris par la mention « À vérifier ».")
        elif phase_no == 7:
            comparison = session.scalar(select(ComparisonVersion).where(
                ComparisonVersion.case_id == case_id, ComparisonVersion.state == "PUBLIEE",
            ).order_by(ComparisonVersion.version_no.desc()).limit(1))
            decision = session.scalar(select(ProjectDecision).where(
                ProjectDecision.case_id == case_id, ProjectDecision.decision_type == "PRIORITAIRE",
                ProjectDecision.comparison_id == (comparison.comparison_id if comparison else ""),
            ).order_by(ProjectDecision.beneficiary_decided_at.desc()).limit(1))
            if comparison is None:
                missing.append("Partagez d'abord une comparaison actuelle avant de formaliser le projet prioritaire.")
            elif decision is None:
                missing.append("Aucun projet prioritaire exprimé par le bénéficiaire n'est consigné.")
            elif not _exists(session, Validation, Validation.case_id == case_id,
                             Validation.object_type == "PROJECT_DECISION", Validation.object_id == decision.decision_id):
                missing.append("La décision prioritaire doit être explicitement partagée au bénéficiaire.")
        elif phase_no == 8:
            comparison = session.scalar(select(ComparisonVersion).where(
                ComparisonVersion.case_id == case_id, ComparisonVersion.state == "PUBLIEE",
            ).order_by(ComparisonVersion.version_no.desc()).limit(1))
            decision = session.scalar(select(ProjectDecision).where(
                ProjectDecision.case_id == case_id, ProjectDecision.decision_type == "PRIORITAIRE",
                ProjectDecision.comparison_id == (comparison.comparison_id if comparison else ""),
            ).order_by(ProjectDecision.beneficiary_decided_at.desc()).limit(1))
            plan = session.scalar(select(ActionPlan).where(ActionPlan.case_id == case_id,
                ActionPlan.state == "PUBLIEE", ActionPlan.decision_id == (decision.decision_id if decision else ""))
                .order_by(ActionPlan.version_no.desc()).limit(1))
            if plan is None:
                missing.append("Partagez un plan d'action fondé sur le projet prioritaire lié à la comparaison actuelle.")
            elif not _exists(session, Validation, Validation.case_id == case_id,
                             Validation.object_type == "ACTION_PLAN", Validation.object_id == plan.action_plan_id):
                missing.append("Le bénéficiaire doit répondre à la dernière version du plan d'action.")
            elif _exists(session, ReviewFlag, ReviewFlag.case_id == case_id,
                         ReviewFlag.object_type == "ACTION_PLAN", ReviewFlag.status == "OPEN"):
                missing.append("Traitez la demande d'ajustement du plan avant de valider cette phase.")
        elif phase_no == 9:
            if not _exists(session, ResultSet, ResultSet.case_id == case_id, ResultSet.state == "CONFIRMEE"):
                missing.append("Les résultats détaillés doivent être partagés et confirmés par le bénéficiaire.")
        elif phase_no == 10:
            if not _exists(session, SynthesisRecord, SynthesisRecord.case_id == case_id, SynthesisRecord.state == "FINALISEE"):
                missing.append("La synthèse finale doit être relue par le bénéficiaire et finalisée par l'accompagnateur.")
        elif phase_no == 11:
            if not _exists(session, ClosureRecord, ClosureRecord.case_id == case_id):
                missing.append("La clôture du bilan et le plan de suivi à six mois doivent être enregistrés.")
        return tuple(missing)


def validate_phase(ctx, case_id: str, phase_no: int, *, note: str,
                   database_url: str | None = None) -> None:
    phase_no = int(phase_no)
    note = str(note or "").strip()
    if len(note) < 12 or len(note) > 2000:
        raise ValueError("Notez en 12 à 2 000 caractères le constat de fin de phase et les points restant à suivre.")
    missing = phase_readiness(ctx, case_id, phase_no, database_url=database_url)
    normalized_note = note.casefold()
    if phase_no in {1, 2, 3} and ("aucune piste" in normalized_note or "aucun métier" in normalized_note):
        missing = tuple(message for message in missing if not any(
            token in message.lower() for token in ("piste", "métier", "metier")
        ))
    if missing:
        raise ValueError("Cette phase n'est pas prête : " + " ".join(missing))
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_VALIDATE")
        state = session.scalar(select(PhaseState).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == phase_no,
        ))
        case = session.get(Case, case_id)
        if state is None or case is None:
            raise ValueError("Cette phase n'est pas initialisée dans le dossier.")
        if state.state == "NON_DISPONIBLE":
            raise ValueError("Cette phase ne peut pas encore être validée : la phase précédente doit être terminée.")
        if state.state in {"VALIDEE", "FIGEE_CLOTURE"}:
            raise ValueError("Cette phase est déjà validée.")
        if phase_no in PHASE_PREVIOUS:
            prior = session.scalar(select(PhaseState).where(
                PhaseState.case_id == case_id, PhaseState.phase_no == PHASE_PREVIOUS[phase_no],
            ))
            if prior is None or prior.state not in {"VALIDEE", "FIGEE_CLOTURE"}:
                raise ValueError("Validez d'abord la phase précédente pour conserver l'ordre du parcours.")
        old_state = state.state
        state.state = "VALIDEE"
        state.current_version_no += 1
        session.add(PhaseEvent(case_id=case_id, phase_no=phase_no, from_state=old_state,
            to_state="VALIDEE", actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            reason=note))
        session.add(Validation(event_key=f"PHASE:{phase_no}:{state.current_version_no}:VALIDEE",
            case_id=case_id, phase_no=phase_no, object_type="PHASE", object_id=str(phase_no),
            object_version=state.current_version_no, actor_type=ctx.actor_role.value,
            actor_id=ctx.actor_id, mode="VALIDATION_ACCOMPAGNATEUR"))
        if phase_no == 0:
            for flag in session.scalars(select(ReviewFlag).where(
                ReviewFlag.case_id == case_id, ReviewFlag.object_type == "CAREER_PHASE0",
                ReviewFlag.status == "OPEN",
            )):
                flag.status = "RESOLU"
        next_phase = PHASE_NEXT.get(phase_no)
        if next_phase is not None:
            next_state = session.scalar(select(PhaseState).where(
                PhaseState.case_id == case_id, PhaseState.phase_no == next_phase,
            ))
            if next_state is not None and next_state.state == "NON_DISPONIBLE":
                next_state.state = "DISPONIBLE"
        case.current_phase = next_phase if next_phase is not None else 11
        if next_phase is not None:
            case.status = "EN_COURS"
        session.add(AuditEvent(case_id=case_id, event_type="PHASE_VALIDATED",
            object_type="PHASE", object_id=str(phase_no), object_version=state.current_version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"phase": phase_no, "note_length": len(note)})))
        session.commit()
