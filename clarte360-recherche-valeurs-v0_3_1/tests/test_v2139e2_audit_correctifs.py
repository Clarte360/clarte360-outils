from pathlib import Path

APP = Path(__file__).parents[1] / "app.py"
TEXT = APP.read_text(encoding="utf-8")


def _widget_source() -> str:
    start = TEXT.index("def open_response_widget")
    end = TEXT.index("def mark_data_change", start)
    return TEXT[start:end]


def test_version_9e2_declared():
    assert 'APP_VERSION = "2.2.0-preproduction"' in TEXT


def test_value_labels_always_keep_initial_written_formulation_option():
    widget = _widget_source()
    assert 'options.extend(["Conserver ma réponse initiale","Utiliser la correction de forme"])' in widget
    assert 'if not expected_value_label: options.append("Conserver ma réponse initiale")' not in widget
    assert widget.count('Conserver ma réponse initiale') >= 4
    assert 'Utiliser la proposition Clarté360' in widget


def test_value_labels_always_keep_initial_voice_transcription_option():
    widget = _widget_source()
    assert 'if not expected_value_label: options.append("Conserver la transcription initiale")' not in widget
    assert 'if not (expected_value_label and proposal): options.append("Conserver la transcription initiale")' not in widget
    assert widget.count('options.append("Conserver la transcription initiale")') >= 3


def test_ctrl_enter_is_installed_for_every_written_field():
    widget = _widget_source()
    assert 'ctrl_enter_button_label = "✓ Valider ma réponse écrite" if (not allow_reformulation and not expected_value_label) else "Préparer et comparer"' in widget
    assert '_install_ctrl_enter_bridge()' in widget
    assert 'if allow_reformulation or expected_value_label:\n        st.caption' not in widget
