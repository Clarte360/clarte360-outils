from pathlib import Path

TEXT=Path(__file__).resolve().parents[1].joinpath('app.py').read_text(encoding='utf-8')

def test_version_139a_and_two_routes():
    assert 'APP_VERSION = "2.1.3.9C-preproduction"' in TEXT
    assert 'module4_route' in TEXT
    assert 'Partir d’une situation que j’ai observée' in TEXT
    assert 'Aidez-moi à trouver une piste' in TEXT

def test_hypothesis_posture_and_module3_boundary():
    assert 'Ces propositions ne sont jamais des conclusions' in TEXT
    assert 'panier Hypothèses' in TEXT
    assert 'depuis le module 3' in TEXT

def test_large_instructions_are_listenable():
    assert 'speak_button(intro,"m4_intro_hypotheses")' in TEXT
    assert 'speak_button(instruction,"m4_way1_instruction")' in TEXT
    assert 'speak_button(instruction,"m4_way2_instruction")' in TEXT

def test_way1_uses_shared_text_voice_validation_engine():
    assert 'open_response_widget(' in TEXT
    assert 'widget_key=f"m4_cycle_{cycle[' in TEXT
    assert 'allow_reformulation=True' in TEXT
    assert 'listen=True' in TEXT
