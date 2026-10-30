from __future__ import annotations

import pytest
from sqlalchemy import select
from streamlit.testing.v1 import AppTest

from clarte360_cp.application.beneficiary import build_beneficiary_home
from clarte360_cp.application.dashboard import build_accompanist_dashboard
from clarte360_cp.application.career_feedback import (
    CareerFeedbackConflict, read_career_phase_feedback, respond_to_career_phase,
)
from clarte360_cp.application.phase_progress import validate_phase
from clarte360_cp.application.beneficiary import build_beneficiary_home
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import CareerItem, Case, PhaseEvent, PhaseState, ReviewFlag, Validation
from tests.helpers import context


def _render_beneficiary_feedback(ctx, view):
    from clarte360_cp.ui.beneficiaire import render_phase
    render_phase(ctx, view, 0)


def _render_accompanist_feedback(ctx, view):
    from clarte360_cp.ui.accompagnateur import render_phase
    render_phase(ctx, view, 0)


def _case(Session):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_VALIDATE"], actor="COACH")
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_VALIDATE"], actor="BEN")
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        case_id = case.case_id
        session.add(CareerItem(case_id=case_id, item_type="EMPLOI", title="Gestionnaire comptable",
            details_json='{"statut_humain":"RELUE_EN_SEANCE","savoirs":"Tenue de comptes"}', status="ACTIVE"))
        session.commit()
    return coach, beneficiary, case_id


def _share(coach, case_id, url):
    validate_phase(coach, case_id, 0, note="Parcours relu avec le bénéficiaire en séance.", database_url=url)


def test_beneficiary_can_confirm_shared_career_once(Session, engine):
    coach, beneficiary, case_id = _case(Session)
    url = str(engine.url)
    _share(coach, case_id, url)
    with Session() as session:
        version = session.scalar(select(PhaseState.current_version_no).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == 0))

    respond_to_career_phase(beneficiary, case_id, version=version, decision="CONFIRME", database_url=url)
    view = build_beneficiary_home(case_id, database_url=url)
    assert view.snapshot.career_feedback == "CONFIRME"
    assert view.snapshot.career_feedback_version == version
    assert len(view.snapshot.career_details) == 1
    with pytest.raises(CareerFeedbackConflict, match="déjà été enregistrée"):
        respond_to_career_phase(beneficiary, case_id, version=version, decision="CONFIRME", database_url=url)


def test_correction_request_reopens_phase_and_is_visible_to_beneficiary(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach, beneficiary, case_id = _case(Session)
    url = str(engine.url)
    _share(coach, case_id, url)
    with Session() as session:
        version = session.scalar(select(PhaseState.current_version_no).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == 0))

    respond_to_career_phase(beneficiary, case_id, version=version,
        decision="CORRECTION_DEMANDEE", comment="Ajouter mon activité de facturation.", database_url=url)
    with Session() as session:
        phase = session.scalar(select(PhaseState).where(PhaseState.case_id == case_id, PhaseState.phase_no == 0))
        case = session.get(Case, case_id)
        event = session.scalar(select(PhaseEvent).where(PhaseEvent.case_id == case_id)
            .order_by(PhaseEvent.at.desc()).limit(1))
        flag = session.scalar(select(ReviewFlag).where(ReviewFlag.case_id == case_id,
            ReviewFlag.object_type == "CAREER_PHASE0"))
        response = session.scalar(select(Validation).where(Validation.case_id == case_id,
            Validation.object_type == "CAREER_PHASE0"))
    assert phase.state == "REOUVERTE"
    assert phase.current_version_no == version + 1
    assert case.current_phase == 0
    assert event.to_state == "REOUVERTE"
    assert flag.status == "OPEN"
    assert response.mode == "CORRECTION_DEMANDEE"
    view = build_beneficiary_home(case_id, database_url=url)
    assert view.snapshot.career_feedback == "CORRECTION_DEMANDEE"
    assert view.snapshot.career_feedback_comment == "Ajouter mon activité de facturation."
    assert view.snapshot.career_details == ()  # the old shared version is no longer presented as current
    assert read_career_phase_feedback(coach, case_id, database_url=url) == {
        "decision": "CORRECTION_DEMANDEE", "comment": "Ajouter mon activité de facturation.",
        "version": version,
    }
    coach_view = build_accompanist_dashboard(case_id, database_url=url)
    app = AppTest.from_function(_render_accompanist_feedback, args=(coach, coach_view), default_timeout=10).run()
    assert not app.exception and not app.error
    assert any("Le bénéficiaire a demandé une correction" in item.value for item in app.warning)
    assert any("Ajouter mon activité de facturation." in item.value for item in app.info)


def test_correction_requires_comment_and_rejects_stale_version(Session, engine):
    coach, beneficiary, case_id = _case(Session)
    url = str(engine.url)
    _share(coach, case_id, url)
    with Session() as session:
        version = session.scalar(select(PhaseState.current_version_no).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == 0))
    with pytest.raises(ValueError, match="correction attendue"):
        respond_to_career_phase(beneficiary, case_id, version=version,
            decision="CORRECTION_DEMANDEE", database_url=url)
    with pytest.raises(CareerFeedbackConflict, match="version partagée a changé"):
        respond_to_career_phase(beneficiary, case_id, version=version - 1,
            decision="CONFIRME", database_url=url)


def test_beneficiary_screen_explains_and_offers_a_clear_response(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach, beneficiary, case_id = _case(Session)
    _share(coach, case_id, str(engine.url))
    view = build_beneficiary_home(case_id, database_url=str(engine.url))

    app = AppTest.from_function(_render_beneficiary_feedback, args=(beneficiary, view), default_timeout=10).run()
    assert not app.exception and not app.error
    assert any("Votre retour sur ce parcours" in item.value for item in app.markdown)
    assert "Je confirme que ce parcours correspond à nos échanges" in app.radio[0].options
    assert "Je demande une correction" in app.radio[0].options
    assert any(item.label == "Transmettre mon retour" for item in app.button)
