"""RC3A: Q validee = formulaire immediatement visible, sans deuxieme clic."""
import pytest
from clarte360_cp.application.preparation import (create_questionnaire_v2, lock_and_publish_questionnaire, read_preparation)
from clarte360_cp.application.orientation import OrientationAccessDenied
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.ui.beneficiaire import _next_action
from tests.helpers import context



@pytest.fixture
def actors(engine, Session):
    acc = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_VALIDATE", "CP_PUBLISH"], actor="ACCOMP-UI-RC3A")
    ben = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT", "CP_BENEFICIARY_VALIDATE"], actor="BEN-UI-RC3A")
    with Session() as session:
        case = CaseRepository(session).open_or_create(acc)
        return str(engine.url), case.case_id, acc, ben


def test_one_coach_action_publishes_without_second_click(actors):
    url, cid, acc, ben = actors
    draft = create_questionnaire_v2(acc, cid, {"APS_OBJECTIF":{"authorized":True,"source_ref":"APS-FAKE", "idea_list":["Idée fictive"]}}, database_url=url)
    assert read_preparation(ben, cid, database_url=url).questionnaire is None
    locked = lock_and_publish_questionnaire(acc, cid, expected_row_version=draft.row_version, database_url=url)
    assert locked.questionnaire_locked and locked.invitation_open
    visible = read_preparation(ben, cid, database_url=url)
    assert visible.invitation_open and visible.questionnaire is not None
    assert len(visible.questionnaire["ideas_active"]) == 1
    assert visible.active_answers is None


def test_one_coach_action_requires_publication_scope(actors):
    url, cid, acc, ben = actors
    draft = create_questionnaire_v2(acc, cid, {}, database_url=url)
    no_publish = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_VALIDATE"], actor="ACCOMP-UI-RC3A")
    with pytest.raises(OrientationAccessDenied):
        lock_and_publish_questionnaire(no_publish, cid, expected_row_version=draft.row_version, database_url=url)
    assert read_preparation(ben, cid, database_url=url).questionnaire is None


def test_preparation_is_priority_above_old_mock_tasks():
    from types import SimpleNamespace
    prep = SimpleNamespace(invitation_open=True, active_answers=None)
    fake_view = SimpleNamespace(snapshot=SimpleNamespace(tasks=[SimpleNamespace(state="EN_COURS", goal="Vieille tache fictive")]))
    action = _next_action(fake_view, prep)
    assert action.page == "b_preparation" and "C-AV1" in action.title


def test_rc3a_ui_combines_lock_and_access():
    from pathlib import Path
    root = Path(__file__).parents[1]
    coach_ui = (root/"clarte360_cp/ui/preparation_rc3.py").read_text(encoding="utf-8")
    assert 'lock_and_publish_questionnaire(ctx,case_id' in coach_ui
    assert 'Valider définitivement et mettre à disposition' in coach_ui
    assert 'aucun email envoyé' not in coach_ui


def test_publication_is_audited_and_versioned_in_one_transaction(actors, Session):
    from sqlalchemy import select
    from clarte360_cp.repositories.models import AuditEvent
    url,cid,acc,ben=actors
    draft=create_questionnaire_v2(acc,cid,{},database_url=url)
    opened=lock_and_publish_questionnaire(acc,cid,expected_row_version=draft.row_version,database_url=url)
    with Session() as db:
        events=list(db.scalars(select(AuditEvent).where(AuditEvent.case_id==cid, AuditEvent.event_type.in_(["CAV_Q_LOCKED","CAV_ACCESS_OPEN"])).order_by(AuditEvent.timestamp)))
        assert len(events)==2
        assert {e.event_type for e in events}=={"CAV_Q_LOCKED","CAV_ACCESS_OPEN"}
        assert {e.object_version for e in events}=={opened.questionnaire_version}


def test_after_r1_mock_task_does_not_override_completed_preparation():
    from types import SimpleNamespace
    prep=SimpleNamespace(invitation_open=True, active_answers={"cav1_done":True,"cav2_done":True})
    fake=SimpleNamespace(snapshot=SimpleNamespace(tasks=[SimpleNamespace(state="EN_COURS",goal="Vieille tache fictive")]))
    action=_next_action(fake,prep)
    assert action.page == "b_home" and "transmis" in action.title
