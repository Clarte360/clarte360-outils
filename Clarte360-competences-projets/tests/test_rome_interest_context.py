from __future__ import annotations

from streamlit.testing.v1 import AppTest

from clarte360_cp.application.beneficiary import build_beneficiary_home
from clarte360_cp.application.rome_interest_context import _mapping, rome_interest_context
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import JobTarget
from tests.helpers import context


def _beneficiary_phase_two(ctx, view):
    from clarte360_cp.ui.beneficiaire import render_phase
    render_phase(ctx, view, 2)


def test_offline_mapping_is_complete_and_only_describes_interest():
    mapping = _mapping()
    assert len(mapping) == 1911
    assert rome_interest_context("M1203") == {
        "rome_code": "M1203", "riasec_code": "CE",
        "source_label": "Corpus de fiches ROME PDF, juin 2026",
    }
    assert rome_interest_context("M1501")["riasec_code"] == "CS"
    assert rome_interest_context("Z9999") is None
    assert all(set(row["riasec_normalized"]) <= set("RIASEC") for row in mapping.values())


def test_beneficiary_sees_rome_interest_context_without_a_match_score(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context()
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        session.add(JobTarget(case_id=case.case_id, rome_code="M1203", rome_label="Comptable",
            status="ACTIVE", selected_order=1))
        session.commit()
        case_id = case.case_id
    view = build_beneficiary_home(case_id, database_url=str(engine.url))
    app = AppTest.from_function(_beneficiary_phase_two,
        args=(beneficiary, view), default_timeout=10).run()
    assert not app.exception and not app.error
    assert any("RIASEC CE" in item.value for item in app.caption)
    assert any("ne dit pas si vous avez les compétences" in item.value for item in app.caption)
