from pathlib import Path

TEXT=(Path(__file__).parents[1]/'app.py').read_text(encoding='utf-8')

def test_version_9e():
    assert 'APP_VERSION = "2.2.0-preproduction-5"' in TEXT

def test_module3_can_open_hypothesis_voluntarily():
    assert 'Examiner une hypothèse conservée' in TEXT
    assert 'Commencer l’examen de cette hypothèse' in TEXT
    assert 'La conserver pour plus tard' in TEXT
    assert 'La supprimer définitivement' in TEXT
    assert 'hypothese_ouverte_module3' in TEXT

def test_visible_vertical_thread():
    assert 'Voir mes questions et réponses validées' in TEXT
    assert '_module4_render_exchange_thread(cycle)' in TEXT
    assert '**Clarté360**' in TEXT and '**Vous**' in TEXT

def test_no_repeat_and_five_question_limit():
    assert 'MODULE4_MAX_VERTICAL_QUESTIONS = 5' in TEXT
    assert '_module4_question_already_asked' in TEXT
    assert '_module4_no_word_answer' in TEXT
    assert 'La même question ne sera pas reposée' in TEXT

def test_atomic_clarification_resolution():
    assert '_module4_resolve_source_track' in TEXT
    assert 'clarification_history' in TEXT
    assert 'st.session_state.values_to_examine=' in TEXT

def test_menu_labels_include_module_word():
    for n in range(1,6):
        assert f'MODULE {n}\\n' in TEXT

def test_structured_reformulation_handling():
    assert 'def assess_response_expression' in TEXT
    assert 'correction_forme' in TEXT
    assert 'reformulation_expression' in TEXT
    assert 'Une proposition ne peut jamais être strictement identique' in TEXT or "Proposition absente ou identique" in TEXT
