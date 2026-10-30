from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from clarte360_cp.application.cv_enrichment import record_cv_ai_analysis
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import AuditEvent
from tests.helpers import context


def _metadata():
    return {
        "provider": "openai", "model": "synthetic-model",
        "prompt_version": "synthetic-prompt-v1", "store": False,
        "source_refs": ["synthetic-cv-ref"], "output_hash": "a" * 64,
        "duration_seconds": 0.25, "input_tokens": 100, "output_tokens": 40,
    }


def test_cv_ai_event_records_traceability_without_document_text(Session, engine):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE"], actor="COACH-CV")
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        case_id = case.case_id

    event_id = record_cv_ai_analysis(coach, case_id, "synthetic-cv-ref", "v2", _metadata(),
                                     database_url=str(engine.url))
    with Session() as session:
        event = session.get(AuditEvent, event_id)
        assert event.event_type == "CV_ENRICHMENT_IA_PROPOSEE"
        assert event.object_type == "GDA_DOCUMENT"
        assert event.object_id == "synthetic-cv-ref"
        metadata = json.loads(event.metadata_json_minimized)
    assert metadata["source_version"] == "v2"
    assert metadata["model"] == "synthetic-model"
    assert metadata["prompt_version"] == "synthetic-prompt-v1"
    assert metadata["output_hash"] == "a" * 64
    assert metadata["status"] == "PROPOSITIONS_A_VALIDER"
    assert "texte du CV" not in event.metadata_json_minimized
    assert "parcours" not in event.metadata_json_minimized


def test_cv_ai_event_rejects_beneficiary_and_incomplete_metadata(Session, engine):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE"], actor="COACH-CV")
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ"], actor="BEN-CV")
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        case_id = case.case_id
    url = str(engine.url)

    with pytest.raises(PermissionError):
        record_cv_ai_analysis(beneficiary, case_id, "synthetic-cv-ref", "v2", _metadata(), database_url=url)
    incomplete = {**_metadata(), "source_refs": []}
    with pytest.raises(ValueError, match="incomplètes"):
        record_cv_ai_analysis(coach, case_id, "synthetic-cv-ref", "v2", incomplete, database_url=url)
    with Session() as session:
        events = session.scalars(select(AuditEvent).where(
            AuditEvent.case_id == case_id, AuditEvent.event_type == "CV_ENRICHMENT_IA_PROPOSEE")).all()
    assert events == []
