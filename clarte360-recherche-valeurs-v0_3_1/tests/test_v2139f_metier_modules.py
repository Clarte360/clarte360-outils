from pathlib import Path
TEXT=Path('app.py').read_text(encoding='utf-8')

def test_version_9f():
    assert 'APP_VERSION = "2.1.3.9F-preproduction"' in TEXT

def test_module3_no_vertical_clarification():
    module3=TEXT[TEXT.index('def render_module_3'):TEXT.index('def _advance_module3')]
    assert 'decision=="clarification_requise"' not in module3
    assert 'm3_clar_' not in module3
    assert 'Questionnaire spécifique Clarté360' in module3

def test_recognized_value_name_has_priority():
    fn=TEXT[TEXT.index('def analyse_concept_nature'):TEXT.index('def _clear_application_exploration')]
    assert 'if present:' in fn
    assert 'decision":"valeur_reconnue"' in fn
    assert 'alerte_definition' in fn
    assert 'un mot isolé' in fn

def test_module2_chat_and_editable():
    fn=TEXT[TEXT.index('def _m2_chat_bubble'):TEXT.index('def _module3_current_work')]
    assert '_m2_chat_bubble("assistant"' in fn
    assert '_m2_chat_bubble("user"' in fn
    assert 'Modifier cette réponse' in fn
    assert 'IA intervient uniquement pour mettre votre réponse en forme, jamais pour vous analyser' in fn

def test_reports_include_time_and_sessions():
    fn=TEXT[TEXT.index('def create_pdf'):TEXT.index('def display_header')]
    assert 'Temps cumulé actif' in fn
    assert 'Dernière activité' in fn
    assert 'duree_active_secondes' in fn

def test_module4_information_popover():
    assert 'Comprendre l’exploration du Module 4' in TEXT
    assert 'Le Module 4 approfondit un terme grâce à un questionnement guidé et vertical' in TEXT

def test_reexamen_does_not_unvalidate_value():
    assert 'original["en_reexamen"]=True' not in TEXT
