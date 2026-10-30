from __future__ import annotations

from streamlit.testing.v1 import AppTest

from clarte360_cp.application.beneficiary import build_beneficiary_home
from clarte360_cp.application.go24 import read_action_plan, save_action_plan
from clarte360_cp.application.go23 import CRITERIA, publish_project_decision, record_project_decision, save_comparison
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import JobTarget, ProjectDecision
from tests.helpers import context


def _render_phase(ctx, view, phase_no):
    from clarte360_cp.ui.beneficiaire import render_phase
    render_phase(ctx, view, phase_no)


def test_go24_beneficiary_can_read_and_confirm_shared_action_plan(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_PUBLISH"])
    beneficiary = context(role="BENEFICIAIRE", scopes=[
        "CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_VALIDATE"
    ], actor="BEN-1")
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        target = JobTarget(case_id=case.case_id, rome_code="M1203", rome_label="Comptable", status="ACTIVE")
        session.add(target)
        session.commit()
        case_id, target_id = case.case_id, target.job_target_id

    save_comparison(coach, case_id, [{"job_target_id": target_id, "criterion": criterion,
        "content": "À vérifier avec une source datée avant de conclure."} for criterion in CRITERIA],
        publish=True, database_url=str(engine.url))
    decision_id = record_project_decision(coach, case_id, job_target_id=target_id,
        decision_type="PRIORITAIRE", wording="Projet prioritaire retenu avec le bénéficiaire.",
        database_url=str(engine.url))
    publish_project_decision(coach, case_id, decision_id=decision_id, database_url=str(engine.url))

    save_action_plan(coach, case_id, [{
        "action": "Réaliser deux entretiens avec des professionnels",
        "due": "Avant le prochain rendez-vous",
        "means": "Préparer une liste de questions",
        "expected": "Comparer les conditions d'exercice",
    }], publish=True, database_url=str(engine.url))
    view = build_beneficiary_home(case_id, database_url=str(engine.url))
    app = AppTest.from_function(_render_phase, args=(beneficiary, view, 8), default_timeout=10).run()
    assert not app.exception and not app.error
    assert any("Mon plan d'action" in item.value for item in app.title)
    assert any("Réaliser deux entretiens" in item.value for item in app.markdown)
    next(button for button in app.button if button.label == "Je confirme avoir relu ce plan").click().run()
    assert not app.exception and not app.error
    assert read_action_plan(coach, case_id, database_url=str(engine.url))["beneficiary_response"] == "EXPLICITE"
