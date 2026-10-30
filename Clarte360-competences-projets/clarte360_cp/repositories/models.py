from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Case(Base):
    __tablename__ = "cases"
    case_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    tool_id: Mapped[str] = mapped_column(String(80), nullable=False, default="competences-projets")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="INITIALISATION")
    current_phase: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retention_class: Mapped[str | None] = mapped_column(String(60), nullable=True)
    purge_state: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    legal_hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow, onupdate=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    __mapper_args__ = {"version_id_col": row_version}
    __table_args__ = (
        CheckConstraint("current_phase IS NULL OR (current_phase >= 0 AND current_phase <= 11)", name="ck_case_phase"),
    )


class CaseContextRef(Base):
    __tablename__ = "case_context_refs"
    context_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), unique=True, nullable=False)
    beneficiary_id: Mapped[str] = mapped_column(String(160), nullable=False)
    action_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prescription_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    participant_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    hub_source: Mapped[str] = mapped_column(String(80), nullable=False, default="GESTION_ACTIONS")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class PhaseState(Base):
    __tablename__ = "phase_states"
    phase_state_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    phase_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    current_version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow, onupdate=utcnow)
    __mapper_args__ = {"version_id_col": row_version}
    __table_args__ = (
        UniqueConstraint("case_id", "phase_no", name="uq_phase_case_no"),
        CheckConstraint("phase_no >= 0 AND phase_no <= 11", name="ck_phase_no"),
    )


class PhaseEvent(Base):
    __tablename__ = "phase_events"
    event_id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    phase_no: Mapped[int] = mapped_column(Integer, nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_state: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class Validation(Base):
    __tablename__ = "validations"
    validation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    phase_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    object_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    mode: Mapped[str] = mapped_column(String(60), nullable=False, default="EXPLICITE")
    at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    __table_args__ = (
        CheckConstraint("actor_type IN ('ACCOMPAGNATEUR','BENEFICIAIRE')", name="ck_validation_actor"),
    )


class Reopening(Base):
    __tablename__ = "reopenings"
    reopening_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    phase_no: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    initiated_by: Mapped[str] = mapped_column(String(160), nullable=False)
    opened_version: Mapped[int] = mapped_column(Integer, nullable=False)
    impact_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class ReviewFlag(Base):
    __tablename__ = "review_flags"
    flag_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    impact_level: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN")


class Artifact(Base):
    __tablename__ = "artifacts"
    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    artifact_class: Mapped[str] = mapped_column(String(60), nullable=False)
    owner_system: Mapped[str] = mapped_column(String(60), nullable=False, default="C&P")
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    visibility_default: Mapped[str] = mapped_column(String(60), nullable=False, default="INTERNE_ACCOMPAGNATEUR")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"
    artifact_version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.artifact_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="BROUILLON")
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    validated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(nullable=True)
    supersedes_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": row_version}
    __table_args__ = (UniqueConstraint("artifact_id", "version_no", name="uq_artifact_version"),)


class FileObject(Base):
    __tablename__ = "file_objects"
    file_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    artifact_version_id: Mapped[str | None] = mapped_column(ForeignKey("artifact_versions.artifact_version_id", ondelete="RESTRICT"), nullable=True)
    logical_path_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    mime: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    storage_status: Mapped[str] = mapped_column(String(30), nullable=False, default="OK")
    __table_args__ = (CheckConstraint("length(sha256) = 64", name="ck_file_sha_len"),)


class ArtifactSourceLink(Base):
    __tablename__ = "artifact_source_links"
    source_link_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    artifact_version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.artifact_version_id", ondelete="RESTRICT"), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    source_id: Mapped[str] = mapped_column(String(160), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(60), nullable=False)
    source_version_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)


class GDAExternalDocument(Base):
    """Document metadata/reference only; GDA retains the binary master."""
    __tablename__ = "gda_external_documents"
    external_document_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    source_version: Mapped[str] = mapped_column(String(100), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_created_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_created_by_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_created_by_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("case_id", "source_ref", "sha256", name="uq_gda_document_source_checksum"),
        CheckConstraint("length(sha256) = 64", name="ck_gda_document_sha_len"),
        CheckConstraint("size_bytes >= 0", name="ck_gda_document_size"),
    )


class GDAExternalDocumentLink(Base):
    """Append-only human decision linking a GDA document to a C&P need."""
    __tablename__ = "gda_external_document_links"
    link_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    external_document_id: Mapped[str] = mapped_column(ForeignKey("gda_external_documents.external_document_id", ondelete="RESTRICT"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    supersedes_link_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    __table_args__ = (CheckConstraint("actor_type = 'ACCOMPAGNATEUR'", name="ck_gda_doc_link_actor"),)


class PublicationEvent(Base):
    __tablename__ = "publication_events"
    publication_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    artifact_version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.artifact_version_id", ondelete="RESTRICT"), nullable=False)
    audience: Mapped[str] = mapped_column(String(60), nullable=False)
    event_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"
    delivery_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    artifact_version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.artifact_version_id", ondelete="RESTRICT"), nullable=False)
    beneficiary_id: Mapped[str] = mapped_column(String(160), nullable=False)
    channel: Mapped[str] = mapped_column(String(60), nullable=False)
    event_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DELIVERED")


class SnapshotQuery(Base):
    __tablename__ = "snapshot_queries"
    query_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    query_json: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class ExternalSnapshot(Base):
    __tablename__ = "external_snapshots"
    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    external_key: Mapped[str] = mapped_column(String(160), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    effective_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    immutable: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class SnapshotUsage(Base):
    __tablename__ = "snapshot_usages"
    usage_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("external_snapshots.snapshot_id", ondelete="RESTRICT"), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    object_version: Mapped[int] = mapped_column(Integer, nullable=False)
    usage_role: Mapped[str] = mapped_column(String(60), nullable=False)


class CareerItem(Base):
    __tablename__ = "career_items"
    career_item_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(240), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_artifact_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_span_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")


class CareerVersion(Base):
    __tablename__ = "career_versions"
    career_version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="BROUILLON")
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    artifact_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    __table_args__ = (UniqueConstraint("case_id", "version_no", name="uq_career_version"),)


class ExplorationIdea(Base):
    __tablename__ = "exploration_ideas"
    idea_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    wording_original: Mapped[str] = mapped_column(Text, nullable=False)
    wording_current: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    accepted_by_beneficiary_at: Mapped[datetime | None] = mapped_column(nullable=True)


class JobTarget(Base):
    __tablename__ = "job_targets"
    job_target_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rome_code: Mapped[str] = mapped_column(String(20), nullable=False)
    rome_label: Mapped[str] = mapped_column(String(240), nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    selected_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    beneficiary_confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class MatchingItem(Base):
    __tablename__ = "matching_items"
    matching_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    job_target_id: Mapped[str] = mapped_column(ForeignKey("job_targets.job_target_id", ondelete="RESTRICT"), nullable=False)
    rome_item_key: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    rome_label: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    final_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    exercise_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_band: Mapped[str | None] = mapped_column(String(30), nullable=True)
    review_required: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class MatchingEvidence(Base):
    __tablename__ = "matching_evidence"
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    matching_id: Mapped[str] = mapped_column(ForeignKey("matching_items.matching_id", ondelete="RESTRICT"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    source_id: Mapped[str] = mapped_column(String(160), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)


class ClarificationItem(Base):
    __tablename__ = "clarification_items"
    clarification_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    matching_id: Mapped[str] = mapped_column(ForeignKey("matching_items.matching_id", ondelete="RESTRICT"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class IntersessionTask(Base):
    __tablename__ = "intersession_tasks"
    task_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    job_target_id: Mapped[str | None] = mapped_column(ForeignKey("job_targets.job_target_id", ondelete="RESTRICT"), nullable=True)
    task_type: Mapped[str] = mapped_column(String(60), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="BROUILLON")
    question_or_goal: Mapped[str] = mapped_column(Text, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class IntersessionResponse(Base):
    __tablename__ = "intersession_responses"
    response_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("intersession_tasks.task_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[str] = mapped_column(String(160), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("task_id", "version_no", name="uq_intersession_response_version"),)


class ComparisonVersion(Base):
    __tablename__ = "comparison_versions"
    comparison_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="BROUILLON")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("case_id", "version_no", name="uq_comparison_version"),)


class ComparisonCell(Base):
    __tablename__ = "comparison_cells"
    cell_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("comparison_versions.comparison_id", ondelete="RESTRICT"), nullable=False)
    job_target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    criterion: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class ProjectDecision(Base):
    __tablename__ = "project_decisions"
    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    comparison_id: Mapped[str | None] = mapped_column(ForeignKey("comparison_versions.comparison_id", ondelete="RESTRICT"), nullable=True)
    job_target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    beneficiary_wording: Mapped[str] = mapped_column(Text, nullable=False)
    decision_type: Mapped[str] = mapped_column(String(30), nullable=False, default="PRIORITAIRE")
    beneficiary_decided_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class ActionPlan(Base):
    __tablename__ = "action_plans"
    action_plan_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    decision_id: Mapped[str] = mapped_column(ForeignKey("project_decisions.decision_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="BROUILLON")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class ActionItem(Base):
    __tablename__ = "action_items"
    action_item_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    action_plan_id: Mapped[str] = mapped_column(ForeignKey("action_plans.action_plan_id", ondelete="RESTRICT"), nullable=False)
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    due_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    means_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResultSet(Base):
    __tablename__ = "result_sets"
    result_set_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="BROUILLON")
    artifact_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class SynthesisRecord(Base):
    __tablename__ = "synthesis_records"
    synthesis_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="BROUILLON")
    artifact_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ClosureRecord(Base):
    __tablename__ = "closure_records"
    closure_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), unique=True, nullable=False)
    action_plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result_set_version: Mapped[int] = mapped_column(Integer, nullable=False)
    synthesis_version: Mapped[int] = mapped_column(Integer, nullable=False)
    closed_by: Mapped[str] = mapped_column(String(160), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class FollowUpPlan(Base):
    __tablename__ = "followup_plans"
    followup_plan_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), unique=True, nullable=False)
    planned_for: Mapped[str] = mapped_column(String(10), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="PREPARE")
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class FollowUpResponse(Base):
    __tablename__ = "followup_responses"
    followup_response_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    followup_plan_id: Mapped[str] = mapped_column(ForeignKey("followup_plans.followup_plan_id", ondelete="RESTRICT"), nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[str] = mapped_column(String(160), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class IntegrationOutbox(Base):
    __tablename__ = "integration_outbox"
    event_id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(60), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_json_minimized: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class IntegrationReceipt(Base):
    __tablename__ = "integration_receipts"
    receipt_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    event_id: Mapped[str] = mapped_column(String(80), nullable=False)
    external_system: Mapped[str] = mapped_column(String(80), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    received_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class IntegrationImport(Base):
    __tablename__ = "integration_imports"
    import_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(36), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    audit_event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    object_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    metadata_json_minimized: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class RetentionMark(Base):
    __tablename__ = "retention_marks"
    retention_mark_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    retention_class: Mapped[str] = mapped_column(String(60), nullable=False)
    purge_state: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    legal_hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    purge_due_at: Mapped[datetime | None] = mapped_column(nullable=True)
    backup_purge_marker: Mapped[str | None] = mapped_column(String(160), nullable=True)


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"
    version: Mapped[str] = mapped_column(String(40), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    description: Mapped[str] = mapped_column(String(240), nullable=False)


# GO22 - Ensemble orientation avant la consolidation du CV. Les versions sont
# append-only et séparées des phases 0..11, qui conservent leurs identifiants.
class OrientationState(Base):
    __tablename__ = "orientation_states"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), primary_key=True)
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    published_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    next_version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow, onupdate=utcnow)
    __mapper_args__ = {"version_id_col": row_version}


class OrientationVersion(Base):
    __tablename__ = "orientation_versions"
    orientation_version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("case_id", "version_no", name="uq_orientation_version"),
        CheckConstraint("state IN ('BROUILLON','PUBLIE_RELECTURE')", name="ck_orientation_state"),
    )


class OrientationFeedback(Base):
    __tablename__ = "orientation_feedback"
    feedback_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    orientation_version_id: Mapped[str] = mapped_column(ForeignKey("orientation_versions.orientation_version_id", ondelete="RESTRICT"), unique=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint("decision IN ('CONFIRME','CORRECTION_DEMANDEE')", name="ck_orientation_feedback"),)


# GO22 RC2 - Questionnaire preparatoire D5 : trois objets et historiques distincts.
# Q : questions approuvees / verrouillees ; R1 : reponses personnelles ;
# R2+ : reponses reprises avec consentement expres en entretien.
class PreparationState(Base):
    __tablename__ = "preparation_states"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), primary_key=True)
    questionnaire_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    response_draft_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    active_response_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    joint_draft_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_response_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    invitation_open: Mapped[bool] = mapped_column(nullable=False, default=False)
    state: Mapped[str] = mapped_column(String(45), nullable=False, default="QUESTIONNAIRE_BROUILLON")
    next_q_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    next_r_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow, onupdate=utcnow)
    __mapper_args__ = {"version_id_col": row_version}


class PreparationQuestionnaire(Base):
    __tablename__ = "preparation_questionnaires"
    questionnaire_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("case_id", "version_no", name="uq_prep_questionnaire_version"),
        CheckConstraint("state IN ('BROUILLON','VERROUILLE')", name="ck_prep_questionnaire_state"),
    )


class PreparationResponse(Base):
    __tablename__ = "preparation_responses"
    response_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    questionnaire_id: Mapped[str] = mapped_column(ForeignKey("preparation_questionnaires.questionnaire_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    parent_response_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confirmation_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    __table_args__ = (
        UniqueConstraint("case_id", "version_no", name="uq_prep_response_version"),
        CheckConstraint("state IN ('BROUILLON','BENEFICIAIRE_VALIDE','REVUE_BROUILLON','REVUE_CONJOINTE')", name="ck_prep_response_state"),
    )


class Cav3Analysis(Base):
    """Immutable internal IA snapshot, tied to the exact Q/R/source fingerprint."""
    __tablename__ = "cav3_analyses"
    analysis_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    response_id: Mapped[str] = mapped_column(ForeignKey("preparation_responses.response_id", ondelete="RESTRICT"), nullable=False)
    response_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class RomeMatchingAnalysis(Base):
    """Immutable IA proposal tied to an exact métier/parcours fingerprint."""
    __tablename__ = "rome_matching_analyses"
    analysis_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    job_target_id: Mapped[str] = mapped_column(ForeignKey("job_targets.job_target_id", ondelete="RESTRICT"), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class RomeMatchingReview(Base):
    """Immutable human-reviewed version; MatchingItem remains a current projection."""
    __tablename__ = "rome_matching_reviews"
    review_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id", ondelete="RESTRICT"), nullable=False)
    job_target_id: Mapped[str] = mapped_column(ForeignKey("job_targets.job_target_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    review_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("case_id", "job_target_id", "version_no", name="uq_rome_matching_review_version"),)
