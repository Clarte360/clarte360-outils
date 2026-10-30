from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from clarte360_cp.framework.config import DATABASE_URL, ensure_runtime_directories
from clarte360_cp.version import SCHEMA_VERSION
from .models import Base, SchemaMigration


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or DATABASE_URL
    if database_url is None:
        ensure_runtime_directories()
    engine = create_engine(url, future=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _connection_record):
            cur = dbapi_connection.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()
    return engine


def _install_sqlite_guards(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    statements = [
        """CREATE TRIGGER IF NOT EXISTS trg_prep_q_no_update BEFORE UPDATE ON preparation_questionnaires BEGIN SELECT RAISE(ABORT,'preparation questionnaire snapshots immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_prep_q_no_delete BEFORE DELETE ON preparation_questionnaires BEGIN SELECT RAISE(ABORT,'preparation questionnaire snapshots immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_prep_r_no_update BEFORE UPDATE ON preparation_responses BEGIN SELECT RAISE(ABORT,'preparation response snapshots immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_prep_r_no_delete BEFORE DELETE ON preparation_responses BEGIN SELECT RAISE(ABORT,'preparation response snapshots immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_cav3_analysis_no_update BEFORE UPDATE ON cav3_analyses BEGIN SELECT RAISE(ABORT,'cav3 analyses immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_cav3_analysis_no_delete BEFORE DELETE ON cav3_analyses BEGIN SELECT RAISE(ABORT,'cav3 analyses immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_rome_matching_analysis_no_update BEFORE UPDATE ON rome_matching_analyses BEGIN SELECT RAISE(ABORT,'ROME matching analyses immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_rome_matching_analysis_no_delete BEFORE DELETE ON rome_matching_analyses BEGIN SELECT RAISE(ABORT,'ROME matching analyses immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_rome_matching_review_no_update BEFORE UPDATE ON rome_matching_reviews BEGIN SELECT RAISE(ABORT,'ROME matching reviews immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_rome_matching_review_no_delete BEFORE DELETE ON rome_matching_reviews BEGIN SELECT RAISE(ABORT,'ROME matching reviews immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_intersession_response_no_update BEFORE UPDATE ON intersession_responses BEGIN SELECT RAISE(ABORT,'intersession responses immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_intersession_response_no_delete BEFORE DELETE ON intersession_responses BEGIN SELECT RAISE(ABORT,'intersession responses immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_followup_response_no_update BEFORE UPDATE ON followup_responses BEGIN SELECT RAISE(ABORT,'followup responses immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_followup_response_no_delete BEFORE DELETE ON followup_responses BEGIN SELECT RAISE(ABORT,'followup responses immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_orientation_version_no_update BEFORE UPDATE ON orientation_versions BEGIN SELECT RAISE(ABORT,'orientation versions immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_orientation_version_no_delete BEFORE DELETE ON orientation_versions BEGIN SELECT RAISE(ABORT,'orientation versions immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_orientation_feedback_no_update BEFORE UPDATE ON orientation_feedback BEGIN SELECT RAISE(ABORT,'orientation feedback immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_orientation_feedback_no_delete BEFORE DELETE ON orientation_feedback BEGIN SELECT RAISE(ABORT,'orientation feedback immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_audit_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'audit_events append-only'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'audit_events append-only'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_validation_no_update BEFORE UPDATE ON validations BEGIN SELECT RAISE(ABORT,'validations append-only'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_validation_no_delete BEFORE DELETE ON validations BEGIN SELECT RAISE(ABORT,'validations append-only'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_delivery_no_update BEFORE UPDATE ON delivery_events BEGIN SELECT RAISE(ABORT,'delivery_events append-only'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_delivery_no_delete BEFORE DELETE ON delivery_events BEGIN SELECT RAISE(ABORT,'delivery_events append-only'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_snapshot_no_update BEFORE UPDATE ON external_snapshots BEGIN SELECT RAISE(ABORT,'external_snapshots immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_snapshot_no_delete BEFORE DELETE ON external_snapshots BEGIN SELECT RAISE(ABORT,'external_snapshots immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_artifact_final_immutable BEFORE UPDATE ON artifact_versions WHEN OLD.state IN ('SOURCE','VALIDE','FINALISE') BEGIN SELECT RAISE(ABORT,'source/validated/finalized artifact immutable'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_job_target_max3_insert BEFORE INSERT ON job_targets WHEN NEW.status='ACTIVE' AND (SELECT COUNT(*) FROM job_targets WHERE case_id=NEW.case_id AND status='ACTIVE') >= 3 BEGIN SELECT RAISE(ABORT,'maximum 3 active job targets'); END""",
        """CREATE TRIGGER IF NOT EXISTS trg_job_target_max3_update BEFORE UPDATE OF status,case_id ON job_targets WHEN NEW.status='ACTIVE' AND (SELECT COUNT(*) FROM job_targets WHERE case_id=NEW.case_id AND status='ACTIVE' AND job_target_id<>NEW.job_target_id) >= 3 BEGIN SELECT RAISE(ABORT,'maximum 3 active job targets'); END""",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.exec_driver_sql(stmt)


def init_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    _upgrade_intersession_task_target(engine)
    _upgrade_matching_item_exercise_level(engine)
    _upgrade_project_decision_comparison(engine)
    _upgrade_gda_document_provenance(engine)
    _install_sqlite_guards(engine)
    factory = sessionmaker(engine, expire_on_commit=False, future=True)
    with factory() as session:
        descriptions = {
            "1": "GO19 initial schema",
            "2": "GO22 additive orientation tables",
            "3": "GO22 RC2 additive preparation Q/R immutable snapshots",
            "4": "GO22 RC3D immutable C-AV3 IA analysis snapshots",
            "5": "GO22 additive immutable ROME matching IA proposals",
            "6": "GO22 additive immutable human-reviewed ROME matching versions",
        "7": "GO22 immutable beneficiary investigation responses",
        "8": "GO24 conclusion deliverables and six-month follow-up",
        "9": "GO23 explicit ROME target on beneficiary investigations",
        "10": "GO27-GO28 GDA external document references and human links",
        "11": "GO22 per-ROME-item exercise level reviewed with beneficiary",
        "12": "GO23 tie project decisions to the published comparison version",
        "13": "GO27-GO28 GDA document depositor provenance",
        }
        for version, description in descriptions.items():
            if int(version) <= int(SCHEMA_VERSION) and not session.get(SchemaMigration, version):
                session.add(SchemaMigration(version=version, description=description))
        session.commit()


def _upgrade_intersession_task_target(engine: Engine) -> None:
    """Add the nullable task-to-ROME relation to existing databases without rewriting history."""
    if not inspect(engine).has_table("intersession_tasks"):
        return
    columns = {column["name"] for column in inspect(engine).get_columns("intersession_tasks")}
    if "job_target_id" in columns:
        return
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE intersession_tasks ADD COLUMN job_target_id VARCHAR(36) "
            "REFERENCES job_targets(job_target_id) ON DELETE RESTRICT"
        )


def _upgrade_matching_item_exercise_level(engine: Engine) -> None:
    """Add the optional human-reviewed exercise level to existing matching rows."""
    if not inspect(engine).has_table("matching_items"):
        return
    columns = {column["name"] for column in inspect(engine).get_columns("matching_items")}
    if "exercise_level" in columns:
        return
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE matching_items ADD COLUMN exercise_level INTEGER NULL")


def _upgrade_project_decision_comparison(engine: Engine) -> None:
    """Add the optional comparison reference without rewriting historical decisions."""
    if not inspect(engine).has_table("project_decisions"):
        return
    columns = {column["name"] for column in inspect(engine).get_columns("project_decisions")}
    if "comparison_id" in columns:
        return
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE project_decisions ADD COLUMN comparison_id VARCHAR(36) "
            "REFERENCES comparison_versions(comparison_id) ON DELETE RESTRICT"
        )


def _upgrade_gda_document_provenance(engine: Engine) -> None:
    """Add optional uploader identity from GDA without inventing it for old references."""
    if not inspect(engine).has_table("gda_external_documents"):
        return
    columns = {column["name"] for column in inspect(engine).get_columns("gda_external_documents")}
    with engine.begin() as conn:
        if "source_created_by_role" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE gda_external_documents ADD COLUMN source_created_by_role VARCHAR(40) NULL"
            )
        if "source_created_by_ref" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE gda_external_documents ADD COLUMN source_created_by_ref VARCHAR(160) NULL"
            )


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False, future=True)


def sqlite_runtime_state(engine: Engine) -> dict[str, str]:
    with engine.connect() as conn:
        journal = conn.execute(text("PRAGMA journal_mode")).scalar_one() if engine.dialect.name == "sqlite" else "n/a"
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar_one() if engine.dialect.name == "sqlite" else "n/a"
        busy = conn.execute(text("PRAGMA busy_timeout")).scalar_one() if engine.dialect.name == "sqlite" else "n/a"
    return {"journal_mode": str(journal).lower(), "foreign_keys": str(fk), "busy_timeout": str(busy)}
