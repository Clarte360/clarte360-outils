from __future__ import annotations

from sqlalchemy import inspect, select

from clarte360_cp.repositories import build_engine, init_database, session_factory
from clarte360_cp.repositories.models import IntersessionTask, SchemaMigration


def test_schema_9_adds_optional_rome_link_without_rewriting_existing_tasks(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'legacy-v8.sqlite3'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE cases (case_id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql("CREATE TABLE job_targets (job_target_id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql("""CREATE TABLE intersession_tasks (
            task_id VARCHAR(36) PRIMARY KEY, case_id VARCHAR(36) NOT NULL,
            task_type VARCHAR(60) NOT NULL, state VARCHAR(30) NOT NULL,
            question_or_goal TEXT NOT NULL, version_no INTEGER NOT NULL,
            created_by VARCHAR(160) NOT NULL, created_at DATETIME NOT NULL
        )""")
        conn.exec_driver_sql("INSERT INTO cases(case_id) VALUES ('case-legacy')")
        conn.exec_driver_sql("""INSERT INTO intersession_tasks
            (task_id, case_id, task_type, state, question_or_goal, version_no, created_by, created_at)
            VALUES ('task-legacy', 'case-legacy', 'ENQUETE_METIER', 'PUBLIEE',
            'Explorer le métier avec un professionnel.', 1, 'coach', '2026-10-23 10:00:00')""")

    init_database(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("intersession_tasks")}
    assert "job_target_id" in columns
    with session_factory(engine)() as session:
        task = session.get(IntersessionTask, "task-legacy")
        migration = session.get(SchemaMigration, "9")
    assert task.question_or_goal == "Explorer le métier avec un professionnel."
    assert task.job_target_id is None
    assert migration is not None
