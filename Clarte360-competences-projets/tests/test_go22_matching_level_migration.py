from __future__ import annotations

from sqlalchemy import inspect

from clarte360_cp.repositories import build_engine, init_database, session_factory
from clarte360_cp.repositories.models import SchemaMigration


def test_schema_11_adds_per_item_level_without_rewriting_existing_matching(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'legacy-v10.sqlite3'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE matching_items (matching_id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql("INSERT INTO matching_items(matching_id) VALUES ('existing-match')")

    init_database(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("matching_items")}
    assert "exercise_level" in columns
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT matching_id, exercise_level FROM matching_items").one() == ("existing-match", None)
    with session_factory(engine)() as session:
        assert session.get(SchemaMigration, "11") is not None
