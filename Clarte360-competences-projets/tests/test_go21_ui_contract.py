from __future__ import annotations

from clarte360_cp.application.beneficiary import build_beneficiary_home
from clarte360_cp.framework.navigation import VALID_PAGES
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import (
    Artifact,
    ArtifactVersion,
    CareerItem,
    IntersessionTask,
    PhaseState,
    PublicationEvent,
)
from clarte360_cp.ui.beneficiaire import FRIENDLY_PHASE, _next_action
from clarte360_cp.ui.spec import BENEFICIARY_PAGES, BENEFICIARY_PHASE_PAGES, BENEFICIARY_STAGE_BY_PHASE
from tests.helpers import context


def _open_beneficiary_case(Session):
    ctx = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT", "CP_BENEFICIARY_VALIDATE", "CP_DOCUMENT_READ_PUBLISHED"], actor="BEN-USER")
    with Session() as session:
        case = CaseRepository(session).open_or_create(ctx)
        return case.case_id


def test_go21_beneficiary_pages_registered_without_replacing_accompanist_pages():
    assert BENEFICIARY_PAGES.issubset(VALID_PAGES)
    assert len(BENEFICIARY_PHASE_PAGES) == 12
    assert "b_home" in BENEFICIARY_PAGES
    assert "dashboard" in VALID_PAGES


def test_beneficiary_main_labels_never_expose_technical_phase_wording():
    assert all(not label.lower().startswith("phase") for label in FRIENDLY_PHASE.values())
    assert set(BENEFICIARY_STAGE_BY_PHASE.values()) == {"Explorer", "Vérifier", "Choisir", "Finaliser"}


def test_unpublished_internal_artifact_is_not_visible_to_beneficiary(Session, engine):
    case_id = _open_beneficiary_case(Session)
    with Session() as session:
        artifact = Artifact(case_id=case_id, artifact_type="NOTE_INTERNE", artifact_class="ARTEFACT_DE_TRAVAIL", owner_system="C&P", visibility_default="INTERNE_ACCOMPAGNATEUR")
        session.add(artifact); session.flush()
        version = ArtifactVersion(artifact_id=artifact.artifact_id, version_no=1, state="BROUILLON", created_by="ACC")
        session.add(version); session.flush(); artifact.current_version_id = version.artifact_version_id
        session.commit()
    view = build_beneficiary_home(case_id, database_url=str(engine.url))
    assert view.snapshot.published_documents == ()


def test_only_explicitly_published_document_surfaces(Session, engine):
    case_id = _open_beneficiary_case(Session)
    with Session() as session:
        artifact = Artifact(case_id=case_id, artifact_type="BOUSSOLE_VALEURS", artifact_class="SOURCE", owner_system="GDA", visibility_default="INTERNE_ACCOMPAGNATEUR")
        session.add(artifact); session.flush()
        version = ArtifactVersion(artifact_id=artifact.artifact_id, version_no=1, state="SOURCE", created_by="ACC")
        session.add(version); session.flush(); artifact.current_version_id = version.artifact_version_id
        session.add(PublicationEvent(case_id=case_id, artifact_version_id=version.artifact_version_id, audience="BENEFICIAIRE", event_key="PUB-1"))
        session.commit()
    view = build_beneficiary_home(case_id, database_url=str(engine.url))
    assert [d.artifact_type for d in view.snapshot.published_documents] == ["BOUSSOLE_VALEURS"]


def test_brouillon_intersession_is_hidden_and_published_task_is_to_do(Session, engine):
    case_id = _open_beneficiary_case(Session)
    with Session() as session:
        session.add(IntersessionTask(case_id=case_id, task_type="TEST", state="BROUILLON", question_or_goal="Interne", created_by="ACC"))
        session.add(IntersessionTask(case_id=case_id, task_type="ENQUETE_METIER", state="PUBLIEE", question_or_goal="Vérifier le terrain", created_by="ACC"))
        session.commit()
    view = build_beneficiary_home(case_id, database_url=str(engine.url))
    assert view.to_do == 1
    assert [t.goal for t in view.snapshot.tasks] == ["Vérifier le terrain"]
    assert _next_action(view).page == "b_intersession"


def test_waiting_beneficiary_phase_becomes_validation_action(Session, engine):
    case_id = _open_beneficiary_case(Session)
    with Session() as session:
        phase = session.query(PhaseState).filter_by(case_id=case_id, phase_no=0).one()
        phase.state = "EN_ATTENTE_BENEFICIAIRE"
        session.commit()
    view = build_beneficiary_home(case_id, database_url=str(engine.url))
    assert view.to_validate == 1
    assert _next_action(view).page == "b_phase_0"


def test_career_items_are_projected_without_cv_reentry(Session, engine):
    case_id = _open_beneficiary_case(Session)
    with Session() as session:
        session.add(CareerItem(case_id=case_id, item_type="EMPLOI", title="Responsable QHSE", organization="Exemple"))
        session.commit()
    view = build_beneficiary_home(case_id, database_url=str(engine.url))
    assert view.snapshot.career_items == ()  # Private phase 0 drafts are hidden.
    with Session() as session:
        phase0 = session.query(PhaseState).filter_by(case_id=case_id, phase_no=0).one()
        phase0.state = "VALIDEE"
        session.commit()
    view = build_beneficiary_home(case_id, database_url=str(engine.url))
    assert view.snapshot.career_items == (("EMPLOI", "Responsable QHSE", "Exemple"),)
    assert view.snapshot.career_details[0].title == "Responsable QHSE"
