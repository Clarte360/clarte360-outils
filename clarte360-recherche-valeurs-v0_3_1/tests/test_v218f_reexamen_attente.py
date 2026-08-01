from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app.py"
TEXT = APP.read_text(encoding="utf-8")


def test_pending_value_is_opened_in_dedicated_mode():
    assert 'work["source"]="examen_attente"' in TEXT
    assert 'work["original_name"]=' in TEXT


def test_pending_value_does_not_block_itself_as_duplicate():
    assert 'own_pending=work.get("source")=="examen_attente"' in TEXT
    assert 'not (own_reexam or own_pending)' in TEXT


def test_migration_does_not_recreate_current_pending_value():
    assert 'active_work_names=set()' in TEXT
    assert 'candidate_variants & active_work_names' in TEXT
