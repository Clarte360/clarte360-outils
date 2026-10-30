from __future__ import annotations

from sqlalchemy import inspect


def test_required_core_tables_present(engine):
    tables=set(inspect(engine).get_table_names())
    required={
        "cases","case_context_refs","phase_states","phase_events","validations","reopenings","review_flags",
        "artifacts","artifact_versions","file_objects","artifact_source_links","publication_events","delivery_events",
        "snapshot_queries","external_snapshots","snapshot_usages","career_items","career_versions","exploration_ideas",
        "job_targets","matching_items","matching_evidence","rome_matching_analyses","rome_matching_reviews","clarification_items","intersession_tasks","comparison_versions",
        "intersession_responses","comparison_cells","project_decisions","action_plans","action_items","result_sets","synthesis_records","closure_records",
        "integration_outbox","integration_receipts","integration_imports","audit_events","retention_marks","schema_migrations",
    }
    assert required <= tables


def test_no_score_total_or_ranking_columns(engine):
    insp=inspect(engine)
    for table in insp.get_table_names():
        cols={c["name"] for c in insp.get_columns(table)}
        assert "score_total" not in cols
        assert "ranking" not in cols
        assert "compatibility_score" not in cols
