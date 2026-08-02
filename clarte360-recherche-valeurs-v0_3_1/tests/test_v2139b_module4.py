from pathlib import Path
TEXT=Path(__file__).resolve().parents[1].joinpath('app.py').read_text(encoding='utf-8')

def test_version_9b():
    assert 'APP_VERSION = "2.1.3.9C-preproduction"' in TEXT

def test_both_paths_are_active():
    assert 'def _module4_generate_way2_question' in TEXT
    assert 'def _module4_render_cycle' in TEXT
    assert '_module4_render_cycle("situation")' in TEXT
    assert '_module4_render_cycle("questions_personnalisees")' in TEXT

def test_shared_question_answer_memory():
    assert 'module4_question_memory' in TEXT
    assert '"question":question,"reponse_validee":answer' in TEXT

def test_one_idea_one_hypothesis_and_basket_only():
    assert 'une idée explorée ne pourra produire qu’une seule hypothèse' in TEXT
    assert 'st.session_state.hypothesis_basket.append(item)' in TEXT
    assert 'values_to_examine.append' not in TEXT[TEXT.index('def _module4_add_hypothesis'):TEXT.index('def _module4_threshold_invitation')]

def test_threshold_rule():
    assert 'hypotheses>=3 and validated+hypotheses>=8' in TEXT
