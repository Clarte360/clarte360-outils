from __future__ import annotations

import sqlite3
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, DatabaseError

from clarte360_cp.repositories import CaseRepository, sqlite_runtime_state
from clarte360_cp.repositories.models import (
    Artifact, ArtifactVersion, AuditEvent, CaseContextRef, ExternalSnapshot, IntersessionResponse, IntersessionTask, JobTarget, RomeMatchingAnalysis, RomeMatchingReview,
    PhaseState, Validation,
)
from .helpers import context


def create_case(Session, **ctx_kwargs):
    with Session() as s:
        c = CaseRepository(s).open_or_create(context(**ctx_kwargs))
        return c.case_id, c.case_code, c.row_version


def test_sqlite_wal_foreign_keys_and_busy_timeout(engine):
    state = sqlite_runtime_state(engine)
    assert state["journal_mode"] == "wal"
    assert state["foreign_keys"] == "1"
    assert int(state["busy_timeout"]) >= 5000


def test_case_open_is_idempotent(Session):
    ctx = context()
    with Session() as s:
        a = CaseRepository(s).open_or_create(ctx)
        first = a.case_id
    with Session() as s:
        b = CaseRepository(s).open_or_create(ctx)
        assert b.case_id == first
        assert len(s.scalars(select(CaseContextRef)).all()) == 1


def test_context_mismatch_refused(Session):
    ctx = context()
    with Session() as s: CaseRepository(s).open_or_create(ctx)
    bad = context(beneficiary="BEN-OTHER")
    from clarte360_cp.repositories.cases import ContextMismatchError
    with Session() as s, pytest.raises(ContextMismatchError):
        CaseRepository(s).open_or_create(bad)


def test_context_requires_all_ids(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO cases(case_id,case_code,tool_id,status,row_version,purge_state,created_at,updated_at) VALUES('C','CP-X','competences-projets','INITIALISATION',1,'ACTIVE',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")
        with pytest.raises(Exception):
            conn.exec_driver_sql("INSERT INTO case_context_refs(context_id,case_id,beneficiary_id,action_id,prescription_id,hub_source,created_at) VALUES('X','C',NULL,'A','P','GESTION_ACTIONS',CURRENT_TIMESTAMP)")


def test_phase_unique_per_case(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        s.add(PhaseState(case_id=case_id, phase_no=0, state="DISPONIBLE"))
        with pytest.raises(IntegrityError): s.commit()


def test_artifact_version_unique(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        art=Artifact(case_id=case_id,artifact_type="TEST",artifact_class="ARTEFACT",created_at=None)
        s.add(art); s.flush()
        s.add_all([
            ArtifactVersion(artifact_id=art.artifact_id,version_no=1,created_by="USR"),
            ArtifactVersion(artifact_id=art.artifact_id,version_no=1,created_by="USR"),
        ])
        with pytest.raises(IntegrityError): s.commit()


def test_validated_artifact_version_is_immutable(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        art=Artifact(case_id=case_id,artifact_type="TEST",artifact_class="ARTEFACT")
        s.add(art); s.flush()
        ver=ArtifactVersion(artifact_id=art.artifact_id,version_no=1,state="VALIDE",created_by="USR",content_json='{"a":1}')
        s.add(ver); s.commit(); vid=ver.artifact_version_id
    with Session() as s:
        ver=s.get(ArtifactVersion,vid); ver.content_json='{"a":2}'
        with pytest.raises(DatabaseError): s.commit()


def test_snapshot_is_immutable(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        x=ExternalSnapshot(case_id=case_id,provider="ROME",resource_type="METIER",external_key="A",payload_json="{}",sha256="a"*64)
        s.add(x); s.commit(); xid=x.snapshot_id
    with Session() as s:
        x=s.get(ExternalSnapshot,xid); x.payload_json='{"changed":true}'
        with pytest.raises(DatabaseError): s.commit()


def test_rome_matching_ai_analysis_is_immutable(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        target=JobTarget(case_id=case_id,rome_code="M1203",rome_label="Comptable")
        s.add(target); s.flush()
        row=RomeMatchingAnalysis(case_id=case_id,job_target_id=target.job_target_id,
            source_fingerprint="a"*64,provider="openai",model="synthetic-model",
            result_json="{}",created_by="USR")
        s.add(row); s.commit(); row_id=row.analysis_id
    with Session() as s:
        row=s.get(RomeMatchingAnalysis,row_id); row.result_json='{"changed":true}'
        with pytest.raises(DatabaseError): s.commit()


def test_audit_is_append_only(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        ev=AuditEvent(case_id=case_id,event_type="TEST",object_type="CASE",object_id=case_id,actor_type="SYSTEME",actor_id="SYS")
        s.add(ev); s.commit(); eid=ev.audit_event_id
    with Session() as s:
        ev=s.get(AuditEvent,eid); ev.event_type="MUTATED"
        with pytest.raises(DatabaseError): s.commit()


def test_validation_only_human_roles(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        s.add(Validation(event_key="v1",case_id=case_id,object_type="X",object_id="1",object_version=1,actor_type="SUPPORT",actor_id="SUP",mode="EXPLICITE"))
        with pytest.raises(IntegrityError): s.commit()


def test_validation_idempotency(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        kw=dict(event_key="v1",case_id=case_id,object_type="X",object_id="1",object_version=1,actor_type="ACCOMPAGNATEUR",actor_id="USR",mode="EXPLICITE")
        s.add(Validation(**kw)); s.commit()
    with Session() as s:
        s.add(Validation(**kw))
        with pytest.raises(IntegrityError): s.commit()


def test_max_three_active_job_targets(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        for i in range(3): s.add(JobTarget(case_id=case_id,rome_code=f"A{i}",rome_label=f"M{i}",status="ACTIVE"))
        s.commit()
        s.add(JobTarget(case_id=case_id,rome_code="A4",rome_label="M4",status="ACTIVE"))
        with pytest.raises(DatabaseError): s.commit()


def test_fourth_inactive_job_target_allowed(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        for i in range(3): s.add(JobTarget(case_id=case_id,rome_code=f"A{i}",rome_label=f"M{i}",status="ACTIVE"))
        s.add(JobTarget(case_id=case_id,rome_code="Z",rome_label="Archive",status="HISTORIQUE"))
        s.commit()



def test_source_artifact_version_is_immutable(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        artifact = Artifact(case_id=case_id, artifact_type="CV_SOURCE", artifact_class="SOURCE")
        s.add(artifact)
        s.flush()
        version = ArtifactVersion(
            artifact_id=artifact.artifact_id,
            version_no=1,
            state="SOURCE",
            content_json='{"source":"cv"}',
            created_by="USR-1",
        )
        s.add(version)
        s.commit()
        vid = version.artifact_version_id
    with Session() as s:
        version = s.get(ArtifactVersion, vid)
        version.content_json = '{"changed":true}'
        with pytest.raises(DatabaseError):
            s.commit()


def test_rome_matching_review_versions_are_immutable(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        target=JobTarget(case_id=case_id,rome_code="M1203",rome_label="Comptable")
        s.add(target); s.flush()
        row=RomeMatchingReview(case_id=case_id,job_target_id=target.job_target_id,version_no=1,
            source_fingerprint="a"*64,review_json="{}",created_by="USR")
        s.add(row); s.commit(); row_id=row.review_id
    with Session() as s:
        row=s.get(RomeMatchingReview,row_id); row.review_json='{"changed":true}'
        with pytest.raises(DatabaseError): s.commit()


def test_intersession_responses_are_immutable(Session):
    case_id, _, _ = create_case(Session)
    with Session() as s:
        task=IntersessionTask(case_id=case_id,task_type="ENQUETE_METIER",state="SOUMISE",
            question_or_goal="Rencontrer un professionnel et vérifier une question.",created_by="USR")
        s.add(task); s.flush()
        row=IntersessionResponse(case_id=case_id,task_id=task.task_id,version_no=1,
            response_json='{"learned":"Constat"}',submitted_by="BEN")
        s.add(row); s.commit(); response_id=row.response_id
    with Session() as s:
        row=s.get(IntersessionResponse,response_id); row.response_json='{"learned":"Changé"}'
        with pytest.raises(DatabaseError): s.commit()
