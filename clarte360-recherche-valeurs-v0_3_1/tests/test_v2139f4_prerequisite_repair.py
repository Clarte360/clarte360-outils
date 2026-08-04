from pathlib import Path
SRC=Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")

def test_version_f4():
    assert 'APP_VERSION = "2.1.9A-preproduction"' in SRC

def test_prerequisite_is_mandatory_and_gates_modules():
    assert 'Ce prérequis est obligatoire pour accéder à l’application.' in SRC
    assert 'if not st.session_state.get("prerequisite_confirmed")' in SRC
    assert '_set_module_status("module_2","disponible","questionnaire")' in SRC

def test_prerequisite_value_by_value_and_no_ai_definition_rewrite():
    assert 'allow_ai_rewrite=False' in SRC
    assert 'Première' in SRC and 'Deuxième' in SRC
    assert 'if not name: return' in SRC
    assert 'if not definition: return' in SRC

def test_code_ctrl_enter():
    assert 'Ctrl + Entrée : valider le code et commencer' in SRC
    assert "['TEXTAREA','INPUT']" in SRC
