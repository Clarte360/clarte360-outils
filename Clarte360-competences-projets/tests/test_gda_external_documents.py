from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import select

from clarte360_cp.application import bootstrap_case
from clarte360_cp.repositories.gda_documents import (
    link_document_to_purpose, record_gda_receipt, save_external_reference,
)
from clarte360_cp.repositories.models import (
    AuditEvent, FileObject, GDAExternalDocumentLink, SchemaMigration,
)
from tests.helpers import context


def _metadata():
    return {
        "source_ref": "gda-ref-1", "source_kind": "DOCUMENT_NON_ASSOCIE",
        "source_version": "3", "display_name": "CV.pdf", "mime_type": "application/pdf",
        "size_bytes": 1234, "sha256": hashlib.sha256(b"source bytes").hexdigest(),
        "created_at": "2026-10-24T10:00:00Z",
    }


def test_schema_10_records_gda_document_metadata_without_copying_binary(Session, engine):
    accomp = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_SOURCE_MANUAL_IMPORT"])
    boot = bootstrap_case(accomp, database_url=str(engine.url))
    with Session() as session:
        row = save_external_reference(session, accomp, boot.case_id, _metadata())
        assert row.source_ref == "gda-ref-1"
        assert row.sha256 == _metadata()["sha256"]
        assert session.scalar(select(FileObject)) is None
        assert session.scalar(select(AuditEvent).where(AuditEvent.event_type == "GDA_DOCUMENT_REFERENCE_SEEN"))
        assert session.scalar(select(SchemaMigration).where(SchemaMigration.version == "10"))


def test_gda_reference_keeps_uploader_provenance_without_copying_binary(Session, engine):
    accomp = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_SOURCE_MANUAL_IMPORT"])
    boot = bootstrap_case(accomp, database_url=str(engine.url))
    metadata = {**_metadata(), "created_by_role": "BENEFICIAIRE", "created_by_ref": "BEN-42"}
    with Session() as session:
        row = save_external_reference(session, accomp, boot.case_id, metadata)
        assert row.source_created_by_role == "BENEFICIAIRE"
        assert row.source_created_by_ref == "BEN-42"
        assert session.scalar(select(FileObject)) is None
        assert session.scalar(select(SchemaMigration).where(SchemaMigration.version == "13"))


def test_schema_13_migration_adds_optional_provenance_to_existing_gda_references():
    from sqlalchemy import create_engine, inspect
    from clarte360_cp.repositories.db import _upgrade_gda_document_provenance

    legacy = create_engine("sqlite://")
    with legacy.begin() as conn:
        conn.exec_driver_sql("""CREATE TABLE gda_external_documents (
            external_document_id VARCHAR(36) PRIMARY KEY,
            source_ref VARCHAR(160) NOT NULL,
            source_created_at VARCHAR(80) NULL)""")
        conn.exec_driver_sql("INSERT INTO gda_external_documents VALUES ('old-ref', 'GDA-1', '2026-10-20')")
    _upgrade_gda_document_provenance(legacy)
    columns = {column["name"] for column in inspect(legacy).get_columns("gda_external_documents")}
    assert {"source_created_by_role", "source_created_by_ref"}.issubset(columns)
    with legacy.connect() as conn:
        row = conn.exec_driver_sql("SELECT source_created_by_role, source_created_by_ref FROM gda_external_documents WHERE external_document_id='old-ref'").one()
    assert row == (None, None)


def test_same_reference_and_checksum_is_idempotent(Session, engine):
    accomp = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_SOURCE_MANUAL_IMPORT"])
    boot = bootstrap_case(accomp, database_url=str(engine.url))
    with Session() as session:
        first = save_external_reference(session, accomp, boot.case_id, _metadata())
        second = save_external_reference(session, accomp, boot.case_id, _metadata())
        assert first.external_document_id == second.external_document_id


def test_only_accompanist_can_link_a_gda_reference_manually(Session, engine):
    accomp = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_SOURCE_MANUAL_IMPORT"])
    boot = bootstrap_case(accomp, database_url=str(engine.url))
    with Session() as session:
        doc = save_external_reference(session, accomp, boot.case_id, _metadata())
        link = link_document_to_purpose(session, accomp, boot.case_id, doc.external_document_id, "CV_SOURCE")
        assert link.actor_id == accomp.actor_id
        assert link.purpose == "CV_SOURCE"
        assert session.scalar(select(GDAExternalDocumentLink).where(GDAExternalDocumentLink.link_id == link.link_id))

    beneficiary = context(role="BENEFICIAIRE", actor="BEN-1",
                          scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT"])
    with Session() as session:
        with pytest.raises(PermissionError, match="Seul l’accompagnateur"):
            link_document_to_purpose(session, beneficiary, boot.case_id, doc.external_document_id, "CV_SOURCE")


def test_forbidden_report_kind_and_unknown_purpose_are_rejected(Session, engine):
    accomp = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_SOURCE_MANUAL_IMPORT"])
    boot = bootstrap_case(accomp, database_url=str(engine.url))
    with Session() as session:
        with pytest.raises(ValueError, match="exclu"):
            save_external_reference(session, accomp, boot.case_id, {**_metadata(), "source_kind": "ONET_REPORT"})
        doc = save_external_reference(session, accomp, boot.case_id, _metadata())
        with pytest.raises(ValueError, match="non reconnu"):
            link_document_to_purpose(session, accomp, boot.case_id, doc.external_document_id, "ONET_REPORT")


def test_gda_deliverable_receipt_is_idempotent_and_conflicts_are_blocked(Session, engine):
    accomp = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_DELIVERABLE_RETURN"])
    boot = bootstrap_case(accomp, database_url=str(engine.url))
    accepted = {"event_id": "event-001", "status": "ACCEPTED", "document_reference_id": "77", "sha256": "a" * 64}
    replayed = {**accepted, "status": "REPLAYED"}
    with Session() as session:
        first = record_gda_receipt(session, accomp, boot.case_id, "event-001", accepted)
        again = record_gda_receipt(session, accomp, boot.case_id, "event-001", replayed)
        assert first.receipt_id == again.receipt_id
        with pytest.raises(ValueError, match="diffère"):
            record_gda_receipt(session, accomp, boot.case_id, "event-001", {**accepted, "sha256": "b" * 64})
