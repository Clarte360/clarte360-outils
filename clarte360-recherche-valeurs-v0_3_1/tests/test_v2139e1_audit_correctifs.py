import ast
from pathlib import Path

APP = Path(__file__).parents[1] / "app.py"
TEXT = APP.read_text(encoding="utf-8")


def _load_function(name):
    tree = ast.parse(TEXT)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    ns = {"re": __import__("re"), "normalize": lambda s: str(s).lower()}
    exec(compile(module, str(APP), "exec"), ns)
    return ns[name]


def test_version_9e1_declared():
    assert 'APP_VERSION = "2.2.0-preproduction"' in TEXT


def test_ctrl_enter_is_a_real_browser_handler():
    assert "def _install_ctrl_enter_bridge" in TEXT
    assert "doc.addEventListener('keydown'" in TEXT
    assert "event.ctrlKey && event.key === 'Enter'" in TEXT
    assert "target.click()" in TEXT
    assert '_install_ctrl_enter_bridge()' in TEXT


def test_difference_classifier_executes_real_cases():
    classify = _load_function("_text_difference_kind")
    assert classify("Je protège mon intégrité.", "Je protège mon intégrité.") == "identique"
    assert classify("Je protège mon intégrité", "Je protège mon intégrité.") == "correction_legere"
    assert classify(
        "Je cherche à préserver mon intégrité physique, être sûr de ne manquer de rien, de pouvoir toujours m’en sortir.",
        "Je cherche à préserver mon intégrité physique, à être sûr de ne manquer de rien et de toujours pouvoir m’en sortir.",
    ) == "correction_legere"
    assert classify("Je veux être tranquille.", "L’autonomie me permet de décider librement de ma trajectoire.") == "reformulation_reelle"


def test_initial_text_and_voice_use_structured_expression_contract():
    widget_start = TEXT.index("def open_response_widget")
    widget_end = TEXT.index("def mark_data_change", widget_start)
    widget = TEXT[widget_start:widget_end]
    assert widget.count("reliable_expression_assessment") >= 3
    assert "correction_forme" in widget
    assert "reformulation_expression" in widget
    assert "clarification_necessaire" in widget
    assert "echec_technique" in widget
