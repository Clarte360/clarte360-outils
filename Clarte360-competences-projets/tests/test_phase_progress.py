from __future__ import annotations

import pytest
from sqlalchemy import select

from clarte360_cp.application.intersession import create_intersession_task
from clarte360_cp.application.phase_progress import phase_readiness, validate_phase
from clarte360_cp.domain.phases import PHASE_FLOW_ORDER, PHASE_NEXT, PHASE_PREVIOUS, phase_display_number
from clarte360_cp.ui.spec import PHASE_SPECS
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import CareerItem, Case, PhaseEvent, PhaseState, JobTarget, IntersessionTask, ResultSet
from tests.helpers import context


def test_phase_validation_requires_evidence_and_unlocks_next(Session, engine):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_VALIDATE"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        case_id = case.case_id
    with pytest.raises(ValueError, match="pas prête"):
        validate_phase(coach, case_id, 0, note="Parcours relu avec le bénéficiaire en séance.", database_url=str(engine.url))

    with Session() as session:
        session.add(CareerItem(case_id=case_id, item_type="EMPLOI", title="Gestionnaire comptable",
            details_json="{}", status="ACTIVE"))
        session.commit()
    assert any("Relisez chaque carte" in blocker for blocker in phase_readiness(
        coach, case_id, 0, database_url=str(engine.url)))
    with Session() as session:
        item = session.query(CareerItem).filter_by(case_id=case_id).one()
        item.details_json = '{"statut_humain":"RELUE_EN_SEANCE"}'
        session.commit()
    validate_phase(coach, case_id, 0, note="Parcours relu avec le bénéficiaire en séance.", database_url=str(engine.url))
    with Session() as session:
        phase0 = session.scalar(select(PhaseState).where(PhaseState.case_id == case_id, PhaseState.phase_no == 0))
        phase1 = session.scalar(select(PhaseState).where(PhaseState.case_id == case_id, PhaseState.phase_no == 1))
        current = session.get(Case, case_id).current_phase
        events = session.scalars(select(PhaseEvent).where(PhaseEvent.case_id == case_id)).all()
    assert phase0.state == "VALIDEE"
    assert phase1.state == "DISPONIBLE"
    assert current == 1
    assert len(events) == 1


def test_go24_follows_a3_results_before_action_plan_without_renumbering_phase_ids(Session, engine):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_VALIDATE"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        case_id = case.case_id
        for phase_no in range(8):
            state = session.scalar(select(PhaseState).where(
                PhaseState.case_id == case_id, PhaseState.phase_no == phase_no,
            ))
            state.state = "VALIDEE"
        result_state = session.scalar(select(PhaseState).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == 9,
        ))
        result_state.state = "DISPONIBLE"
        plan_state = session.scalar(select(PhaseState).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == 8,
        ))
        plan_state.state = "NON_DISPONIBLE"
        session.add(ResultSet(case_id=case_id, version_no=1, state="CONFIRMEE"))
        session.commit()

    assert PHASE_FLOW_ORDER[8:10] == (9, 8)
    assert PHASE_PREVIOUS[8] == 9
    assert PHASE_NEXT[9] == 8
    assert tuple(spec.phase_no for spec in PHASE_SPECS[-4:]) == (9, 8, 10, 11)
    assert phase_display_number(9) == 9 and phase_display_number(8) == 10
    validate_phase(coach, case_id, 9,
        note="Les résultats détaillés ont été relus et confirmés avec le bénéficiaire.",
        database_url=str(engine.url))

    with Session() as session:
        result_state = session.scalar(select(PhaseState).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == 9,
        ))
        plan_state = session.scalar(select(PhaseState).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == 8,
        ))
        current = session.get(Case, case_id).current_phase
    assert result_state.state == "VALIDEE"
    assert plan_state.state == "DISPONIBLE"
    assert current == 8


def test_go23_investigation_phase_waits_for_beneficiary_return_and_debrief(Session, engine):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_VALIDATE"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        case_id = case.case_id
        session.add(CareerItem(case_id=case_id, item_type="EMPLOI", title="Gestionnaire comptable",
            details_json='{"statut_humain":"RELUE_EN_SEANCE"}', status="ACTIVE"))
        session.commit()
    # Establish the prerequisite phases using the valid no-piste path in this synthetic case.
    for phase_no, note in ((0, "Parcours relu avec le bénéficiaire en séance."),
                           (1, "Aucune piste précise n'est identifiée à ce stade."),
                           (2, "Aucun métier ROME n'est retenu à ce stade."),
                           (3, "Aucun métier ROME n'est rapproché avant l'investigation."),
                           (4, "Les incertitudes utiles ont été examinées et consignées.")):
        validate_phase(coach, case_id, phase_no, note=note, database_url=str(engine.url))
    create_intersession_task(coach, case_id, task_type="ENQUETE_METIER",
        goal="Vérifier les missions exercées dans un poste de comptable.", database_url=str(engine.url))
    assert any("débriefée" in x for x in phase_readiness(coach, case_id, 5, database_url=str(engine.url)))
    with pytest.raises(ValueError, match="pas prête"):
        validate_phase(coach, case_id, 5, note="Retour d'enquête à reprendre en séance.", database_url=str(engine.url))


def test_phase_progress_rejects_beneficiary_mutation(Session, engine):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ"])
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_VALIDATE"], actor="BEN-1")
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        case_id = case.case_id
        session.add(CareerItem(case_id=case_id, item_type="EMPLOI", title="Gestionnaire comptable",
            details_json='{"statut_humain":"RELUE_EN_SEANCE"}', status="ACTIVE"))
        session.commit()
    with pytest.raises(PermissionError):
        validate_phase(beneficiary, case_id, 0, note="Je valide ma phase de parcours professionnel.", database_url=str(engine.url))


def test_go23_phase5_requires_one_debriefed_investigation_per_selected_job(Session, engine):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_VALIDATE"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        case_id = case.case_id
        jobs = [JobTarget(case_id=case_id, rome_code=code, rome_label=label, status="ACTIVE")
                for code, label in (("M1203", "Comptable"), ("M1501", "Assistant RH"))]
        session.add_all(jobs)
        session.commit()
        job_ids = [job.job_target_id for job in jobs]

    blockers = phase_readiness(coach, case_id, 5, database_url=str(engine.url))
    assert len([item for item in blockers if "au moins une investigation" in item]) == 2

    with Session() as session:
        for job_id in job_ids:
            session.add(IntersessionTask(case_id=case_id, job_target_id=job_id,
                task_type="ENQUETE_METIER", state="CLOTUREE",
                question_or_goal="Échanger avec un professionnel du métier.",
                created_by=coach.actor_id))
        session.commit()
    assert not phase_readiness(coach, case_id, 5, database_url=str(engine.url))
