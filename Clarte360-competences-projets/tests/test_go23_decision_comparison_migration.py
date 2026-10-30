from __future__ import annotations

from sqlalchemy import inspect

from clarte360_cp.repositories import build_engine, init_database, session_factory
from clarte360_cp.repositories.models import SchemaMigration


def test_schema_12_links_new_decisions_and_preserves_legacy_rows(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'legacy-v11.sqlite3'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE project_decisions (decision_id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql("INSERT INTO project_decisions(decision_id) VALUES ('historical-decision')")

    init_database(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("project_decisions")}
    assert "comparison_id" in columns
    with engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT decision_id, comparison_id FROM project_decisions"
        ).one() == ("historical-decision", None)
    with session_factory(engine)() as session:
        assert session.get(SchemaMigration, "12") is not None
