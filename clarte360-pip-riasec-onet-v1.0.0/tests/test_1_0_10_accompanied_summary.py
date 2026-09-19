from pathlib import Path


def test_1_0_10_result_summary_evolved_to_final_contract_without_raw_answers():
    src = Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")
    block = src[src.index("def _accompanied_final_payload"):src.index("def _save_if_accompanied")]
    assert "holland_code" in block
    assert "scores" in block
    assert "ranking" in block
    assert "scoring_version" in block
    assert "documents" in block
    assert "answers" not in block


def test_1_0_10_preserves_unsaved_guard():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "public_has_unsaved_work" in app
    assert "render_browser_unsaved_guard" in app


def test_1_0_10_preserves_hub_validation_layer():
    connector = Path("clarte360_pip/connectors/gestion_actions.py").read_text(encoding="utf-8")
    assert "validate_epoch_window" in connector
    assert "validate_safe_id" in connector
    assert "validate_string_list" in connector
    assert "PIP_RESULT_READ" in connector


def test_1_0_10_version_bumped_from_real_1_0_9_base():
    from clarte360_pip.version import APP_VERSION
    assert APP_VERSION == "1.0.10-l1-vps-hub-ready-guard-accompagnement"
