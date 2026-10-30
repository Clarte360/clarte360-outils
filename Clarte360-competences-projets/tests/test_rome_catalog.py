from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from clarte360_cp.application.rome_catalog import decide_rome_target, prepare_rome_target, read_rome_targets
from clarte360_cp.connectors.france_travail import RomeMetierSnapshot
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import AuditEvent, ExternalSnapshot
from tests.helpers import context


class FakeRomeClient:
    def fetch_fiche_metier(self, code, *, force_refresh=False):
        return RomeMetierSnapshot(code, {"rome": {"code_rome": code, "intitule": "Comptable"},
            "competences": {"savoirs": {"categories": [{"libelle": "Domaines d'expertise", "items": [
                {"libelle": "Comptabilité client", "code_ogr": "117781"}]}]}}, "version": "synthetic-rome"},
            "FRANCE_TRAVAIL", "ROME_FICHE_METIER", datetime(2026, 10, 23, tzinfo=timezone.utc), "synthetic-rome", None)


def test_official_fiche_is_saved_as_proposal_then_requires_session_confirmation(Session, engine):
    ctx = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(ctx)
        case_id = case.case_id
    proposal = prepare_rome_target(ctx, case_id, "m1203", client=FakeRomeClient(), database_url=str(engine.url))
    assert proposal["status"] == "PROPOSITION"
    unchanged = prepare_rome_target(ctx, case_id, "m1203", client=FakeRomeClient(), database_url=str(engine.url))
    assert unchanged["unchanged"] is True
    assert unchanged["snapshot_id"] == proposal["snapshot_id"]
    with Session() as session:
        assert session.scalar(select(func.count()).select_from(ExternalSnapshot).where(
            ExternalSnapshot.case_id == case_id, ExternalSnapshot.external_key == "M1203")) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.case_id == case_id, AuditEvent.event_type == "ROME_FICHE_REFRESH_UNCHANGED")) == 1
    targets = read_rome_targets(ctx, case_id, database_url=str(engine.url))
    assert targets[0]["label"] == "Comptable"
    status = decide_rome_target(ctx, case_id, proposal["job_target_id"], accept=True, database_url=str(engine.url))
    assert status == "ACTIVE"
