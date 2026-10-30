from __future__ import annotations

from streamlit.testing.v1 import AppTest

from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import JobTarget, ProjectDecision
from tests.helpers import context


def _render_action_plan(ctx, case_id):
    from clarte360_cp.ui.accompagnateur import render_action_plan
    render_action_plan(ctx, case_id)


def _render_results(ctx, case_id):
    from clarte360_cp.ui.accompagnateur import render_detailed_results
    render_detailed_results(ctx, case_id)


def _render_synthesis(ctx, case_id):
    from clarte360_cp.ui.accompagnateur import render_final_synthesis
    render_final_synthesis(ctx, case_id)


def _render_closure(ctx, case_id):
    from clarte360_cp.ui.accompagnateur import render_bilan_closure
    render_bilan_closure(ctx, case_id)


def test_go24_accompanist_screens_expose_distinct_action_result_synthesis_and_closure_steps(
    Session, engine, monkeypatch
):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_PUBLISH"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        target = JobTarget(case_id=case.case_id, rome_code="M1203", rome_label="Comptable", status="ACTIVE")
        session.add(target)
        session.commit()
        case_id, target_id = case.case_id, target.job_target_id
        session.add(ProjectDecision(case_id=case_id, job_target_id=target_id,
            decision_type="PRIORITAIRE", beneficiary_wording="Projet prioritaire retenu avec le bénéficiaire."))
        session.commit()

    checks = (
        (_render_action_plan, "Plan d'action relié au projet prioritaire", "Enregistrer et partager au bénéficiaire"),
        (_render_results, "Résultats détaillés du bilan", "Partager pour relecture du bénéficiaire"),
        (_render_synthesis, "Synthèse finale", "Partager pour relecture du bénéficiaire"),
        (_render_closure, "Clôture du bilan et suivi à six mois", "Enregistrer le suivi à six mois"),
    )
    for render, heading, action in checks:
        app = AppTest.from_function(render, args=(coach, case_id), default_timeout=10).run()
        assert not app.exception and not app.error
        assert any(heading in element.value for element in app.markdown)
        assert any(element.label == action for element in app.button)
