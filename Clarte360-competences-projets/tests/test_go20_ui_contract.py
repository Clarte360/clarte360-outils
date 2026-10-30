from __future__ import annotations

from clarte360_cp.framework.navigation import VALID_PAGES, set_page
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.dashboard import DashboardRepository
from clarte360_cp.repositories.models import Artifact, ArtifactVersion, IntersessionTask, ReviewFlag
from clarte360_cp.ui.spec import (
    ACCOMPAGNATEUR_PAGES,
    FORBIDDEN_SOURCE_TYPES,
    PHASE_BY_NO,
    PHASE_PAGES,
    PHASE_SPECS,
    SOURCE_CARDS,
    choose_next_action,
    phase_page,
)
from tests.helpers import context


def _open_case(Session):
    ctx = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(ctx)
        return case.case_id, case.row_version


def _snapshot(Session, case_id):
    with Session() as session:
        return DashboardRepository(session).load(case_id)


def _add_artifact(Session, case_id, artifact_type, *, state="SOURCE", version_no=1):
    with Session() as session:
        artifact = Artifact(
            case_id=case_id,
            artifact_type=artifact_type,
            artifact_class="SOURCE",
            owner_system="C&P",
            visibility_default="INTERNE_ACCOMPAGNATEUR",
        )
        session.add(artifact)
        session.flush()
        version = ArtifactVersion(
            artifact_id=artifact.artifact_id,
            version_no=version_no,
            state=state,
            created_by="USR-1",
        )
        session.add(version)
        session.flush()
        artifact.current_version_id = version.artifact_version_id
        session.commit()


def test_go20_page_registry_is_complete_and_navigation_only():
    assert len(PHASE_SPECS) == 12
    assert set(PHASE_PAGES) == {f"phase_{i}" for i in range(12)}
    assert {"dashboard", "documents", "entry_context", "entry_sources"}.issubset(ACCOMPAGNATEUR_PAGES)
    assert ACCOMPAGNATEUR_PAGES.issubset(VALID_PAGES)

    state = {"navigation_page": "dashboard", "case_row_version": 7, "business_flag": "UNCHANGED"}
    set_page(state, "phase_3")
    assert state["navigation_page"] == "phase_3"
    assert state["case_row_version"] == 7
    assert state["business_flag"] == "UNCHANGED"


def test_phase_specs_keep_go05_screen_codes_and_go07_validation_roles():
    assert PHASE_BY_NO[0].screen_codes == ("A-P0-01", "A-P0-02")
    assert PHASE_BY_NO[3].screen_codes == ("A-P3-01", "A-P3-02")
    assert PHASE_BY_NO[5].screen_codes == ("A-P5-01", "A-P5-02")
    assert PHASE_BY_NO[10].screen_codes == ("A-P10-01",)
    assert PHASE_BY_NO[11].screen_codes == ("A-P11-01",)
    assert PHASE_BY_NO[3].validation_label == "Accompagnateur"
    assert "Bénéficiaire" in PHASE_BY_NO[7].validation_label
    assert "Accompagnateur" in PHASE_BY_NO[10].validation_label


def test_source_cards_are_six_upstream_plus_shared_cv_and_exclude_onet_public():
    codes = [code for code, _ in SOURCE_CARDS]
    assert codes == [
        "APS_OBJECTIF",
        "BOUSSOLE_VALEURS",
        "MOTEURS_PRO",
        "PREFERENCES_PRO",
        "IPIP_REPORT",
        "PIP_REPORT",
        "CV_SOURCE",
    ]
    assert len(codes) == 7
    assert not FORBIDDEN_SOURCE_TYPES.intersection(codes)
    assert "ONET_REPORT" in FORBIDDEN_SOURCE_TYPES


def test_go22_first_business_screen_is_ideas_even_without_cv(Session):
    case_id, row_version = _open_case(Session)
    snapshot = _snapshot(Session, case_id)
    action = choose_next_action(snapshot)
    assert action.page == "entry_ideas"
    assert "idées" in action.title.lower()
    assert snapshot.current_phase == 0
    assert len(snapshot.phase_states) == 12
    assert snapshot.document_summaries[-1].artifact_type == "CV_SOURCE"
    assert not snapshot.document_summaries[-1].present

    with Session() as session:
        case = session.get(__import__("clarte360_cp.repositories.models", fromlist=["Case"]).Case, case_id)
        assert case.row_version == row_version


def test_go22_with_cv_still_starts_with_ideas_until_initial_directions_shared(Session):
    case_id, _ = _open_case(Session)
    _add_artifact(Session, case_id, "CV_SOURCE")
    snapshot = _snapshot(Session, case_id)
    action = choose_next_action(snapshot)
    assert action.page == "entry_ideas"
    assert snapshot.document_summaries[-1].present
    assert snapshot.document_summaries[-1].current_state == "SOURCE"
    assert snapshot.document_summaries[-1].version_no == 1


def test_submitted_intersession_is_prioritized_for_debrief(Session):
    case_id, _ = _open_case(Session)
    _add_artifact(Session, case_id, "CV_SOURCE")
    with Session() as session:
        session.add(IntersessionTask(
            case_id=case_id,
            task_type="ENQUETE_METIER",
            state="SOUMISE",
            question_or_goal="Vérifier les conditions d'exercice",
            created_by="USR-1",
        ))
        session.commit()
    snapshot = _snapshot(Session, case_id)
    assert snapshot.active_tasks == 1
    assert snapshot.submitted_tasks == 1
    assert choose_next_action(snapshot).page == "phase_5"


def test_open_review_flag_becomes_next_action_when_no_submitted_task(Session):
    case_id, _ = _open_case(Session)
    _add_artifact(Session, case_id, "CV_SOURCE")
    with Session() as session:
        session.add(ReviewFlag(
            case_id=case_id,
            object_type="CAREER_VERSION",
            object_id="CV-1",
            reason="Source amont plus récente",
            impact_level="MAJEUR",
            status="OPEN",
        ))
        session.commit()
    snapshot = _snapshot(Session, case_id)
    assert snapshot.open_flags == 1
    action = choose_next_action(snapshot)
    assert action.page == "phase_0"
    assert "revoir" in action.title.lower()


def test_forbidden_onet_and_public_reports_never_surface_as_documents(Session):
    case_id, _ = _open_case(Session)
    _add_artifact(Session, case_id, "ONET_REPORT")
    _add_artifact(Session, case_id, "PIP_PUBLIC_REPORT")
    snapshot = _snapshot(Session, case_id)
    assert all(item.artifact_type not in FORBIDDEN_SOURCE_TYPES for item in snapshot.document_summaries)
    assert snapshot.other_documents_count == 0


def test_results_and_synthesis_are_distinct_phase_contracts():
    assert PHASE_BY_NO[9].short_label == "Résultats"
    assert PHASE_BY_NO[10].short_label == "Synthèse"
    assert phase_page(9) != phase_page(10)
    assert PHASE_BY_NO[9].screen_codes != PHASE_BY_NO[10].screen_codes


def test_comparison_contract_is_qualitative_without_ranking_language():
    spec = PHASE_BY_NO[6]
    text = f"{spec.label} {spec.finality}".lower()
    assert "sans score" in text
    assert "classement automatique" in text
