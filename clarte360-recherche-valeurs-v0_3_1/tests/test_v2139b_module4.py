from pathlib import Path
TEXT=Path(__file__).resolve().parents[1].joinpath('app.py').read_text(encoding='utf-8')

def test_version_9b():
    assert 'APP_VERSION = "2.2.0-preproduction-4"' in TEXT

def test_both_paths_are_active():
    assert 'def _module4_generate_way2_question' in TEXT
    assert 'def _module4_render_cycle' in TEXT
    assert '_module4_render_cycle("situation")' in TEXT
    assert '_module4_render_cycle("questions_personnalisees")' in TEXT

def test_shared_question_answer_memory():
    assert 'module4_question_memory' in TEXT
    assert '"question":question,"reponse_validee":answer' in TEXT

def test_one_exploration_can_keep_multiple_hypotheses_in_basket_only():
    assert 'une même exploration pourra conduire à plusieurs hypothèses retenues' in TEXT
    assert 'Décidez séparément pour chaque hypothèse' in TEXT
    assert '_module4_apply_hypothesis_decisions' in TEXT
    assert 'st.session_state.hypothesis_basket.append(item)' in TEXT
    assert 'values_to_examine.append' not in TEXT[TEXT.index('def _module4_add_hypothesis'):TEXT.index('def _module4_threshold_invitation')]

def test_threshold_rule():
    assert 'hypotheses>=3 and validated+hypotheses>=8' in TEXT
