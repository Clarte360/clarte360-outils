from __future__ import annotations

from clarte360_cp.application.live_sync import build_live_sync, record_sync_probe
from clarte360_cp.repositories.cases import CaseRepository
from tests.helpers import context


def test_live_sync_probe_changes_revision_and_is_shared(Session, engine):
    ctx = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(ctx)
        case_id = case.case_id
    before = build_live_sync(case_id, database_url=str(engine.url))
    after = record_sync_probe(case_id, actor_type="ACCOMPAGNATEUR", actor_id="USR-1", label="signal A", database_url=str(engine.url))
    assert after.revision != before.revision
    assert after.probe_count == 1
    assert after.latest_probe_label == "signal A"


def test_live_sync_records_reciprocal_actor_without_overwrite(Session, engine):
    ctx = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(ctx)
        case_id = case.case_id
    record_sync_probe(case_id, actor_type="ACCOMPAGNATEUR", actor_id="ACC-1", label="depuis accompagnateur", database_url=str(engine.url))
    state = record_sync_probe(case_id, actor_type="BENEFICIAIRE", actor_id="BEN-1", label="depuis bénéficiaire", database_url=str(engine.url))
    assert state.probe_count == 2
    assert state.latest_probe_actor == "BENEFICIAIRE"
    assert state.latest_probe_label == "depuis bénéficiaire"
