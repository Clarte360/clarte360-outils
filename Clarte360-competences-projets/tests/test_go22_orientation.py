from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DatabaseError, IntegrityError

from clarte360_cp.application.beneficiary import build_beneficiary_home
from clarte360_cp.application.dashboard import build_accompanist_dashboard
from clarte360_cp.application.orientation import (
    OrientationAccessDenied, OrientationConflict, feedback_orientation,
    publish_orientation, read_orientation, save_orientation,
)
from clarte360_cp.domain.orientation import (
    MOTORS, PREFERENCES, RIASEC, blank_orientation,
    new_direction, new_idea, valid_orientation,
)
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import (
    AuditEvent, CareerItem, OrientationFeedback, OrientationState,
    OrientationVersion, PhaseState, ReviewFlag, SchemaMigration, Validation,
)
from clarte360_cp.ui.spec import ACCOMPAGNATEUR_PAGES, BENEFICIARY_PAGES, choose_next_action
from tests.helpers import context


ACC_SCOPES = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_PUBLISH", "CP_VALIDATE"]
BEN_SCOPES = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_VALIDATE", "CP_DOCUMENT_READ_PUBLISHED"]


@pytest.fixture
def prepared(Session, engine):
    accomp = context(scopes=ACC_SCOPES, actor="COACH-GO22")
    beneficiary = context(role="BENEFICIAIRE", scopes=BEN_SCOPES, actor="BEN-GO22")
    with Session() as session:
        case = CaseRepository(session).open_or_create(accomp)
        case_id = case.case_id
    return str(engine.url), case_id, accomp, beneficiary


def save(prepared, document=None, expected=None):
    url, cid, coach, _ben = prepared
    if expected is None:
        expected = read_orientation(coach, cid, database_url=url).current_version
    return save_orientation(coach, cid, document or blank_orientation(),
                            expected_row_version=expected, database_url=url)


def publish(prepared, revision):
    url, cid, coach, _ben = prepared
    return publish_orientation(coach, cid, expected_row_version=revision, database_url=url)


def test_go22_navigation_precedes_cv_and_preserves_twelve_phases(prepared, Session):
    url, cid, _, _ = prepared
    assert {"entry_ideas", "entry_reperes", "entry_directions"}.issubset(ACCOMPAGNATEUR_PAGES)
    assert "b_orientation" in BENEFICIARY_PAGES
    dashboard = build_accompanist_dashboard(cid, database_url=url)
    assert choose_next_action(dashboard.snapshot).page == "entry_ideas"
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(PhaseState).where(PhaseState.case_id == cid)) == 12


def test_validation_accepts_all_ten_motors_and_avoids_rank_logic():
    content = blank_orientation()
    content["reviews"]["MOTEURS_PRO"]["retained"] = list(MOTORS)
    content["reviews"]["PREFERENCES_PRO"]["retained"] = list(PREFERENCES)
    content["reviews"]["PIP_REPORT"]["retained"] = list(RIASEC)
    assert len(valid_orientation(content)["reviews"]["MOTEURS_PRO"]["retained"]) == 10
    content["reviews"]["BOUSSOLE_VALEURS"]["retained"] = ["Autonomie", "Utilité", "Créativité", "Justice"]
    with pytest.raises(ValueError, match="trois valeurs"):
        valid_orientation(content)


def test_invalid_origins_and_scores_cannot_be_inserted():
    content = blank_orientation()
    content["ideas"].append(new_idea("être nourrice"))
    content["ideas"][0]["origin"] = "EMPLOYEUR"
    with pytest.raises(ValueError):
        valid_orientation(content)
    content["ideas"][0]["origin"] = "EXPRESSION_SEANCE"
    content["compatibility_score"] = 99
    with pytest.raises(ValueError, match="Structure"):
        valid_orientation(content)


def test_no_idea_yet_is_publishable_without_cv(prepared):
    url, cid, coach, ben = prepared
    doc = blank_orientation()
    doc["no_idea_yet"] = True
    draft = save(prepared, doc)
    shared = publish(prepared, draft.current_version)
    assert shared.published_version is not None
    assert read_orientation(ben, cid, database_url=url).current["no_idea_yet"]
    assert choose_next_action(build_accompanist_dashboard(cid, database_url=url).snapshot).page == "entry_sources"


def test_publish_refuses_silent_no_idea_and_no_expression(prepared):
    draft = save(prepared)
    with pytest.raises(ValueError, match="Notez une idée"):
        publish(prepared, draft.current_version)


def test_draft_and_enterprise_information_are_hidden_until_publication(prepared):
    url, cid, coach, ben = prepared
    doc = blank_orientation()
    doc["ideas"].append(new_idea("aide vétérinaire"))
    doc["enterprise"] = {"present": True,
                          "wording": "Responsable QHSE", "source_label": "Volet entreprise APS daté",
                          "choice": "NE_SOUHAITE_PAS"}
    draft = save(prepared, doc)
    beneficiary_view = read_orientation(ben, cid, database_url=url)
    assert beneficiary_view.published is None
    assert beneficiary_view.current["ideas"] == []
    assert not beneficiary_view.current["enterprise"]["present"]
    assert draft.current["enterprise"]["choice"] == "NE_SOUHAITE_PAS"
    shared = publish(prepared, draft.current_version)
    ben_view = read_orientation(ben, cid, database_url=url)
    assert ben_view.published["ideas"][0]["current"] == "aide vétérinaire"
    assert ben_view.published["enterprise"]["choice"] == "NE_SOUHAITE_PAS"
    assert shared.published_version == ben_view.published_version


def test_published_snapshot_stays_visible_during_private_new_draft(prepared):
    url, cid, _coach, ben = prepared
    doc = blank_orientation()
    doc["ideas"].append(new_idea("travailler avec des enfants"))
    draft = save(prepared, doc)
    published = publish(prepared, draft.current_version)
    newer = read_orientation(prepared[2], cid, database_url=url).current
    newer["ideas"].append(new_idea("activité indépendante"))
    edit = save(prepared, newer, published.current_version)
    assert edit.has_draft
    bview = read_orientation(ben, cid, database_url=url)
    assert len(bview.published["ideas"]) == 1
    assert len(bview.current["ideas"]) == 1
    assert bview.published_version == published.published_version


def test_stale_editor_is_rejected_without_overwriting_document(prepared):
    url, cid, coach, _ben = prepared
    doc = blank_orientation()
    doc["ideas"].append(new_idea("coaching"))
    first = save(prepared, doc, expected=0)
    with pytest.raises(OrientationConflict):
        save(prepared, doc, expected=0)
    assert read_orientation(coach, cid, database_url=url).current_version == first.current_version


def test_confirm_requires_beneficiary_and_generates_single_validation(prepared, Session):
    url, cid, coach, ben = prepared
    doc = blank_orientation()
    doc["ideas"].append(new_idea("formation professionnelle"))
    draft = save(prepared, doc)
    pub = publish(prepared, draft.current_version)
    reply = feedback_orientation(ben, cid, published_version=pub.published_version,
                                 decision="CONFIRME", database_url=url)
    assert reply.feedback == "CONFIRME"
    with Session() as s:
        vals = list(s.scalars(select(Validation).where(Validation.case_id == cid, Validation.object_type == "ORIENTATION")))
        assert len(vals) == 1 and vals[0].actor_type == "BENEFICIAIRE"
    with pytest.raises(OrientationConflict, match="déjà"):
        feedback_orientation(ben, cid, published_version=pub.published_version,
                             decision="CONFIRME", database_url=url)


def test_correction_is_traced_not_sent_to_enterprise(prepared, Session):
    url, cid, coach, ben = prepared
    doc = blank_orientation()
    doc["ideas"].append(new_idea("management de projet"))
    pub = publish(prepared, save(prepared, doc).current_version)
    reply = feedback_orientation(ben, cid, published_version=pub.published_version,
                                 decision="CORRECTION_DEMANDEE", comment="Je pensais à la formation.", database_url=url)
    assert reply.feedback == "CORRECTION_DEMANDEE"
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(ReviewFlag).where(ReviewFlag.case_id == cid,
                           ReviewFlag.status == "OPEN", ReviewFlag.object_type == "ORIENTATION")) == 1
        assert s.scalar(select(func.count()).select_from(Validation).where(Validation.case_id == cid,
                           Validation.object_type == "ORIENTATION")) == 0
        events = list(s.scalars(select(AuditEvent).where(AuditEvent.case_id == cid,
                                                         AuditEvent.event_type == "ORIENTATION_FEEDBACK")))
        assert all("formation" not in x.metadata_json_minimized for x in events)
    newer = read_orientation(coach, cid, database_url=url).current
    newer["ideas"][0]["current"] = "formation"
    edit = save(prepared, newer)
    publish(prepared, edit.current_version)
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(ReviewFlag).where(ReviewFlag.case_id == cid,
                            ReviewFlag.status == "OPEN", ReviewFlag.object_type == "ORIENTATION")) == 0
        assert s.scalar(select(func.count()).select_from(ReviewFlag).where(ReviewFlag.case_id == cid,
                            ReviewFlag.status == "RESOLU", ReviewFlag.object_type == "ORIENTATION")) == 1


def test_comment_is_required_for_correction(prepared):
    url, cid, coach, ben = prepared
    d = blank_orientation();d["no_idea_yet"] = True
    pub = publish(prepared, save(prepared, d).current_version)
    with pytest.raises(ValueError, match="correction attendue"):
        feedback_orientation(ben, cid, published_version=pub.published_version,
                             decision="CORRECTION_DEMANDEE", comment="", database_url=url)


def test_original_wording_and_provenance_cannot_be_rewritten(prepared):
    url, cid, coach, ben = prepared
    d = blank_orientation()
    d["ideas"].append(new_idea("nourrice", "EXPRESSION_SEANCE"))
    save(prepared, d)
    current = read_orientation(coach, cid, database_url=url).current
    current["ideas"][0]["original"] = "assistante maternelle"
    with pytest.raises(ValueError, match="mots initiaux"):
        save(prepared, current)
    current["ideas"][0]["original"] = "nourrice"
    current["ideas"].clear()
    with pytest.raises(ValueError, match="effacée"):
        save(prepared, current)


def test_roles_and_case_context_protected(prepared):
    url, cid, coach, ben = prepared
    d = blank_orientation(); d["no_idea_yet"] = True
    with pytest.raises(OrientationAccessDenied):
        save_orientation(ben, cid, d, expected_row_version=0, database_url=url)
    with pytest.raises(OrientationAccessDenied):
        feedback_orientation(coach, cid, published_version=0, decision="CONFIRME", database_url=url)
    wrong = context(scopes=ACC_SCOPES, beneficiary="BEN-OTHER")
    with pytest.raises(OrientationAccessDenied, match="concordant"):
        read_orientation(wrong, cid, database_url=url)


def test_immutable_orientation_versions_feedback_and_additive_schema(prepared, Session):
    url, cid, coach, ben = prepared
    d = blank_orientation(); d["no_idea_yet"] = True
    pub = publish(prepared, save(prepared, d).current_version)
    feedback_orientation(ben, cid, published_version=pub.published_version,
                         decision="CONFIRME", database_url=url)
    with Session() as s:
        v = s.scalar(select(OrientationVersion).where(OrientationVersion.case_id == cid).limit(1))
        v.content_json = "{}"
        with pytest.raises(DatabaseError):
            s.commit()
        s.rollback()
        fb = s.scalar(select(OrientationFeedback).where(OrientationFeedback.case_id == cid))
        fb.decision = "CORRECTION_DEMANDEE"
        with pytest.raises(DatabaseError):
            s.commit()
    with Session() as s:
        assert s.get(SchemaMigration, "2") is not None
        assert s.scalar(select(func.count()).select_from(PhaseState).where(PhaseState.case_id == cid)) == 12


def test_direction_is_not_rome_and_no_limit_of_three_ideas(prepared):
    d = blank_orientation()
    for idx in range(6):
        d["ideas"].append(new_idea(f"idée n°{idx+1}"))
    d["directions"].append(new_direction("Accompagnement / transmission"))
    result = valid_orientation(d)
    assert len(result["ideas"]) == 6
    assert len(result["directions"]) == 1
    assert "rome_code" not in result["directions"][0]


def test_beneficiary_count_and_home_action_take_publication_into_account(prepared):
    url, cid, coach, ben = prepared
    d = blank_orientation(); d["no_idea_yet"] = True
    pub = publish(prepared, save(prepared, d).current_version)
    home = build_beneficiary_home(cid, database_url=url)
    assert home.to_validate >= 1
    assert home.snapshot.orientation_published_version == pub.published_version
    assert home.snapshot.orientation_feedback is None


def test_new_ideas_and_directions_never_activate_without_beneficiary_choice():
    idea = new_idea("aide vétérinaire")
    direction = new_direction("Métiers auprès des animaux")
    assert idea["decision"] == "A_DECIDER"
    assert direction["decision"] == "A_DECIDER"
    document = blank_orientation()
    document["ideas"].append(idea)
    document["directions"].append(direction)
    assert valid_orientation(document)["ideas"][0]["decision"] == "A_DECIDER"


def test_enterprise_default_position_does_not_assume_beneficiary_agreement():
    doc = blank_orientation()
    doc["ideas"].append(new_idea("être nourrice"))
    doc["enterprise"] = {"present": True, "wording": "Responsable QHSE",
                         "source_label": "APS entreprise - document reçu", "choice": "A_DECIDER"}
    assert valid_orientation(doc)["enterprise"]["choice"] == "A_DECIDER"
