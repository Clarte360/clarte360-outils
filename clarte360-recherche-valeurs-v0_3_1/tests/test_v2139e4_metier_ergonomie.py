from pathlib import Path
TEXT=Path(__file__).resolve().parents[1].joinpath('app.py').read_text(encoding='utf-8')

def test_version_e4():
    assert 'APP_VERSION = "2.2.0-preproduction"' in TEXT

def test_quatre_orientations_module3():
    for label in (
        'Poursuivre l’examen maintenant dans le Module 3',
        'Conserver dans Valeurs à examiner',
        'Envoyer vers À explorer — Module 4',
        'Placer dans À revoir en séance',
    ):
        assert label in TEXT

def test_transition_atomique_inclut_module4():
    assert 'if keep!="a_explorer"' in TEXT
    assert 'st.session_state.clarification_tracks=' in TEXT
    assert 'def _send_work_to_explore' in TEXT
    assert 'def _save_work_for_later' in TEXT

def test_consignes_questions_ouvertes_et_mot():
    assert 'question_kind: str="open"' in TEXT
    assert 'Si rien ne vous vient, vous pouvez répondre « Je ne sais pas » ou « Je ne vois pas »' in TEXT
    assert "N'hésitez pas à répondre à l'oral" in TEXT

def test_cartes_modules_professionnelles():
    assert 'cl360-module-card' in TEXT
    assert '("MODULE 3","Valider ou revoir une valeur")' in TEXT
