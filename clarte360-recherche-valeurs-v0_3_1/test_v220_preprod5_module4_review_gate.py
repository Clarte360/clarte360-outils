from pathlib import Path

APP = Path(__file__).with_name('app.py').read_text(encoding='utf-8')

def test_review_pending_cannot_seed_new_question():
    assert 'can_seed_question = stage in {"", "question"}' in APP
    assert 'if cycle.get("stage")=="synthese_globale_pending":' in APP
    seed = APP.index('can_seed_question = stage in {"", "question"}')
    pending = APP.index('if cycle.get("stage")=="synthese_globale_pending":', seed)
    assert seed < pending
    assert 'can_seed_question and voie=="questions_personnalisees"' in APP
    assert 'can_seed_question and voie=="situation"' in APP
    assert 'can_seed_question and voie=="piste_clarifier"' in APP

def test_manual_review_sets_pending_and_clears_question():
    assert 'cycle["review_trigger"]="demande_beneficiaire"; cycle["stage"]="synthese_globale_pending"; cycle["question"]=""; st.rerun()' in APP

def test_five_question_guard_still_present():
    assert '_module4_vertical_count(cycle) >= MODULE4_MAX_VERTICAL_QUESTIONS' in APP
    assert 'cycle["review_trigger"]="limite_cinq_questions"' in APP
