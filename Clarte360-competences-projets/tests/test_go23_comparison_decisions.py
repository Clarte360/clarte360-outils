from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from clarte360_cp.application.go23 import (
    CRITERIA, publish_comparison, publish_project_decision, read_go23, record_project_decision, save_comparison,
)
from clarte360_cp.application.go24 import read_action_plan, save_action_plan
from clarte360_cp.repositories.beneficiary import BeneficiaryRepository
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import JobTarget, PhaseEvent, PhaseState
from tests.helpers import context


def _render_comparison(ctx, case_id):
    from clarte360_cp.ui.accompagnateur import render_project_comparison
    render_project_comparison(ctx, case_id)


def _render_decision(ctx, case_id):
    from clarte360_cp.ui.accompagnateur import render_project_decision
    render_project_decision(ctx, case_id)


def _case_with_targets(Session):
    accompanist = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_PUBLISH"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(accompanist)
        targets = [JobTarget(case_id=case.case_id, rome_code=f"M120{i}", rome_label=label,
                             status="ACTIVE", selected_order=i)
                   for i, label in enumerate(("Comptable", "Gestionnaire de paie"), start=1)]
        session.add_all(targets); session.commit()
        return accompanist, case.case_id, [target.job_target_id for target in targets]


def _complete_comparison(ctx, case_id, targets, db_url):
    cells = [{"job_target_id": target, "criterion": criterion,
              "content": "À vérifier avec une source datée avant de tirer une conclusion."}
             for target in targets for criterion in CRITERIA]
    save_comparison(ctx, case_id, cells, publish=True, database_url=db_url)


def test_go23_comparison_versions_are_private_until_explicit_publication(Session, engine):
    ctx, case_id, targets = _case_with_targets(Session)
    save_comparison(ctx, case_id, [{"job_target_id": targets[0], "criterion": CRITERIA[0],
        "content": "Expérience de tenue et de contrôle des comptes."}], database_url=str(engine.url))
    with Session() as session:
        hidden = BeneficiaryRepository(session).load(case_id)
        assert hidden.comparison_cells == ()
    with pytest.raises(ValueError, match="Complétez chaque critère"):
        publish_comparison(ctx, case_id, database_url=str(engine.url))
    _complete_comparison(ctx, case_id, targets, str(engine.url))
    version = read_go23(ctx, case_id, database_url=str(engine.url))["comparison_version"]
    assert version == 2
    with Session() as session:
        visible = BeneficiaryRepository(session).load(case_id)
    assert len(visible.comparison_cells) == len(targets) * len(CRITERIA)
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ"], actor="BEN-1")
    save_comparison(ctx, case_id, [{"job_target_id": targets[0], "criterion": CRITERIA[0], "content": "Brouillon privé."}], database_url=str(engine.url))
    beneficiary_view = read_go23(beneficiary, case_id, database_url=str(engine.url))
    assert beneficiary_view["comparison_state"] == "PUBLIEE"
    assert len(beneficiary_view["comparison_cells"]) == len(targets) * len(CRITERIA)


def test_go23_records_beneficiary_priority_and_optional_alternative(Session, engine):
    ctx, case_id, targets = _case_with_targets(Session)
    _complete_comparison(ctx, case_id, targets, str(engine.url))
    reason = "Le bénéficiaire retient cette piste après comparaison de ses conditions et de ses acquis."
    record_project_decision(ctx, case_id, job_target_id=targets[0], decision_type="PRIORITAIRE",
                            wording=reason, database_url=str(engine.url))
    record_project_decision(ctx, case_id, job_target_id=targets[1], decision_type="ALTERNATIVE",
                            wording="Cette option reste ouverte si la vérification du marché confirme sa faisabilité.",
                            database_url=str(engine.url))
    with Session() as session:
        hidden = BeneficiaryRepository(session).load(case_id)
    assert hidden.project_decision is None
    for decision_id in read_go23(ctx, case_id, database_url=str(engine.url))["decision_ids"].values():
        publish_project_decision(ctx, case_id, decision_id=decision_id, database_url=str(engine.url))
    with Session() as session:
        view = BeneficiaryRepository(session).load(case_id)
    assert view.project_decision == (targets[0], reason)
    assert view.project_alternative[0] == targets[1]


def test_go23_rejects_unknown_target_and_unqualified_role(Session, engine):
    ctx, case_id, targets = _case_with_targets(Session)
    _complete_comparison(ctx, case_id, targets, str(engine.url))
    with pytest.raises(ValueError, match="raisons exprimées"):
        record_project_decision(ctx, case_id, job_target_id=targets[0], decision_type="PRIORITAIRE",
                                wording="Trop court", database_url=str(engine.url))
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ"], actor="BEN-1")
    with pytest.raises(PermissionError):
        record_project_decision(beneficiary, case_id, job_target_id=targets[0], decision_type="PRIORITAIRE",
                                wording="Le bénéficiaire a bien exprimé cette décision en séance.",
                                database_url=str(engine.url))


def test_go23_rejects_duplicate_comparison_cells(Session, engine):
    ctx, case_id, targets = _case_with_targets(Session)
    cells = [{"job_target_id": targets[0], "criterion": CRITERIA[0], "content": "Première lecture."},
             {"job_target_id": targets[0], "criterion": CRITERIA[0], "content": "Seconde lecture."}]
    with pytest.raises(ValueError, match="Une seule observation"):
        save_comparison(ctx, case_id, cells, database_url=str(engine.url))


def test_go23_new_comparison_requires_choice_to_be_reconfirmed_before_go24(Session, engine):
    ctx, case_id, targets = _case_with_targets(Session)
    _complete_comparison(ctx, case_id, targets, str(engine.url))
    decision_id = record_project_decision(ctx, case_id, job_target_id=targets[0],
        decision_type="PRIORITAIRE",
        wording="Le bénéficiaire retient cette piste après discussion de ses acquis et conditions.",
        database_url=str(engine.url))
    publish_project_decision(ctx, case_id, decision_id=decision_id, database_url=str(engine.url))
    save_action_plan(ctx, case_id, [{"action": "Préparer la suite du projet"}], publish=True,
                     database_url=str(engine.url))
    with Session() as session:
        for phase_no in (6, 7, 8):
            phase = session.query(PhaseState).filter_by(case_id=case_id, phase_no=phase_no).one()
            phase.state = "VALIDEE"
        session.commit()

    # A revised, explicitly shared comparison is a new basis for the choice.
    _complete_comparison(ctx, case_id, targets, str(engine.url))
    current = read_go23(ctx, case_id, database_url=str(engine.url))
    assert current["decision_out_of_date"] is True
    assert "PRIORITAIRE" not in current["decisions"]
    with pytest.raises(ValueError, match="comparaison a changé"):
        save_action_plan(ctx, case_id, [{"action": "Préparer la suite du projet"}],
                         database_url=str(engine.url))
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ"], actor="BEN-1")
    beneficiary_plan = read_action_plan(beneficiary, case_id, database_url=str(engine.url))
    assert beneficiary_plan["items"] == ()
    assert beneficiary_plan["out_of_date"] is True
    with Session() as session:
        states = {row.phase_no: row.state for row in session.query(PhaseState).filter(
            PhaseState.case_id == case_id).all()}
        reopened = session.query(PhaseEvent).filter_by(case_id=case_id, to_state="REOUVERTE").count()
    assert states[6] == states[7] == states[8] == "REOUVERTE"
    assert reopened == 3


def test_go23_accompanist_screens_save_and_publish_comparison_and_decision(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    ctx, case_id, targets = _case_with_targets(Session)

    app = AppTest.from_function(_render_comparison, args=(ctx, case_id), default_timeout=10).run()
    assert not app.exception and not app.error
    first = next(widget for widget in app.text_area if widget.label == CRITERIA[0])
    first.set_value("Expérience avérée en clôture comptable. Source : parcours enrichi, séance du 23/10/2026.")
    next(widget for widget in app.text_area if widget.label == CRITERIA[1]).set_value(
        "Aucune obligation officielle confirmée à ce stade ; vérification à poursuivre.")
    next(widget for widget in app.text_area if widget.label == CRITERIA[5]).set_value(
        "Horaires de clôture à vérifier avec une enquête métier.")
    for job_id in targets:
        for criterion in CRITERIA:
            widget = next(w for w in app.text_area if w.key == f"go23_{job_id}_{CRITERIA.index(criterion)}")
            if not widget.value.strip():
                widget.set_value("À vérifier avec une source datée avant de tirer une conclusion.")
    next(widget for widget in app.button if widget.label == "Enregistrer et partager au bénéficiaire").click().run()
    assert not app.exception and not app.error
    assert read_go23(ctx, case_id, database_url=str(engine.url))["comparison_state"] == "PUBLIEE"

    choice = AppTest.from_function(_render_decision, args=(ctx, case_id), default_timeout=10).run()
    assert not choice.exception and not choice.error
    next(widget for widget in choice.text_area if widget.label == "Raisons et conditions formulées par le bénéficiaire").set_value(
        "Le bénéficiaire choisit cette piste car elle mobilise ses acquis et correspond à ses conditions recherchées.")
    next(widget for widget in choice.checkbox if widget.label == "Cette position a été exprimée par le bénéficiaire en séance").check()
    next(widget for widget in choice.button if widget.label == "Enregistrer cette décision").click().run()
    assert not choice.exception and not choice.error
    next(widget for widget in choice.button if widget.label == "Partager projet prioritaire").click().run()
    with Session() as session:
        beneficiary = BeneficiaryRepository(session).load(case_id)
    assert beneficiary.project_decision[0] == targets[0]
