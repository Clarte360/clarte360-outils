from __future__ import annotations

import pytest

from clarte360_cp.application.intersession import (
    close_intersession_task, create_intersession_task, read_intersession_tasks,
    save_intersession_draft, submit_intersession_response,
)
from clarte360_cp.application.orientation import OrientationAccessDenied
from clarte360_cp.application.beneficiary import build_beneficiary_home
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import JobTarget
from tests.helpers import context


def test_targeted_investigation_draft_submission_and_debrief_are_versioned(Session, engine):
    accompanist = context()
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(accompanist)
        case_id = case.case_id
        target = JobTarget(case_id=case_id, rome_code="M1203", rome_label="Comptable", status="ACTIVE")
        session.add(target)
        session.commit()
        target_id = target.job_target_id

    task = create_intersession_task(accompanist, case_id, task_type="OFFRES_EMPLOI",
        goal="Comparer deux offres et noter les compétences et conditions d’accès demandées.",
        job_target_id=target_id,
        database_url=str(engine.url))
    assert task["state"] == "PUBLIEE"
    assert task["job_target_id"] == target_id
    assert task["job_target_label"] == "Comptable"
    assert read_intersession_tasks(beneficiary, case_id, database_url=str(engine.url))[0]["task_id"] == task["task_id"]
    beneficiary_home = build_beneficiary_home(case_id, database_url=str(engine.url))
    assert beneficiary_home.snapshot.tasks[0].job_label == "Comptable"
    assert beneficiary_home.snapshot.tasks[0].job_code == "M1203"

    draft = save_intersession_draft(beneficiary, case_id, task["task_id"], source="France Travail",
        consulted_on="2026-10-23", learned="Deux offres demandent la clôture mensuelle.", project_impact="Je souhaite préciser mon expérience de clôture.",
        database_url=str(engine.url))
    assert draft["state"] == "EN_COURS"
    assert draft["response"]["response_state"] == "BROUILLON"

    with pytest.raises(ValueError, match="source, ce que vous avez appris"):
        submit_intersession_response(beneficiary, case_id, task["task_id"], source="", consulted_on="2026-10-23",
            learned="Constat", project_impact="Impact", database_url=str(engine.url))

    sent = submit_intersession_response(beneficiary, case_id, task["task_id"], source="France Travail",
        consulted_on="2026-10-23", learned="Deux offres demandent la clôture mensuelle.",
        project_impact="Je souhaite préciser mon expérience de clôture.", database_url=str(engine.url))
    assert sent["state"] == "SOUMISE"
    assert sent["response"]["response_state"] == "TRANSMISE"
    with pytest.raises(OrientationAccessDenied):
        submit_intersession_response(beneficiary, case_id, task["task_id"], source="x", consulted_on="2026-10-23",
            learned="x", project_impact="x", database_url=str(engine.url))

    close_intersession_task(accompanist, case_id, task["task_id"], database_url=str(engine.url))
    closed = read_intersession_tasks(accompanist, case_id, database_url=str(engine.url))[0]
    assert closed["state"] == "CLOTUREE"
    assert closed["response"]["learned"].startswith("Deux offres")
