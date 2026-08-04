from pathlib import Path

APP = Path(__file__).parents[1] / "app.py"
TEXT = APP.read_text(encoding="utf-8")


def _bridge_source() -> str:
    start = TEXT.index("def _ctrl_enter_marker")
    end = TEXT.index("def open_response_widget", start)
    return TEXT[start:end]


def _widget_source() -> str:
    start = TEXT.index("def open_response_widget")
    end = TEXT.index("def mark_data_change", start)
    return TEXT[start:end]


def test_version_9e3_declared():
    assert 'APP_VERSION = "2.1.3.9F4-preproduction"' in TEXT


def test_ctrl_enter_uses_unique_marker_for_each_response_widget():
    widget = _widget_source()
    assert '_ctrl_enter_marker(f"{base}_typed_{edit_mode}", ctrl_enter_button_label)' in widget
    bridge = _bridge_source()
    assert 'data-clarte360-response-key' in bridge
    assert 'data-clarte360-target-label' in bridge


def test_ctrl_enter_is_scoped_between_current_and_next_marker():
    bridge = _bridge_source()
    assert "const current = markers[currentIndex];" in bridge
    assert "const next = markers[currentIndex + 1] || null;" in bridge
    assert "if (!follows(button, active)) return false;" in bridge
    assert "if (next && follows(button, next)) return false;" in bridge
    assert "const target = buttons.find" in bridge
    assert "const target = buttons.find((button) =>\n          !button.disabled" not in bridge
