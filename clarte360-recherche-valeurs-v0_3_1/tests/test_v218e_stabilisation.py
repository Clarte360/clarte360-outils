from pathlib import Path
import ast

APP=Path(__file__).resolve().parents[1]/'app.py'
TEXT=APP.read_text(encoding='utf-8')

def test_version_8e():
    assert 'APP_VERSION = "2.1.3.8E-preproduction"' in TEXT

def test_four_mandatory_decisions():
    for token in ['valeur_reconnue','clarification_requise','valeur_absente_possible','formulation_non_valeur']:
        assert token in TEXT
    assert 'Conclut obligatoirement par l\'une des quatre décisions métier de la 8E' in TEXT

def test_duplicate_and_single_active_list_guards():
    assert 'def _active_value_location' in TEXT
    assert 'def _remove_value_from_active_lists' in TEXT
    assert 'Elle ne peut pas être ajoutée une seconde fois' in TEXT
    assert 'une valeur = un état actuel = une seule liste active' in TEXT

def test_phrase_is_not_saved_as_value_name():
    assert 'def _looks_like_value_label' in TEXT
    assert 'Aucune donnée n’a été enregistrée' in TEXT
    assert 'module 4 « Rechercher une nouvelle valeur avec Clarté360 »' in TEXT

def test_normalisation_removes_articles_and_punctuation():
    fn=TEXT[TEXT.index('def _normalise_value_name'):TEXT.index('def _looks_like_value_label')]
    assert "l['’]" in fn
    assert 'le\\s+' in fn and 'la\\s+' in fn
    assert 'local_value_matches' in fn

def test_series_buttons_are_explicit():
    assert 'Abandonner la valeur en cours' in TEXT
    assert 'Arrêter la saisie des valeurs restantes' in TEXT
    assert 'Quitter sans modifier' not in TEXT
    assert 'celles déjà complètement validées' in TEXT

def test_clarification_context_is_persisted():
    assert '"clarifications":deepcopy(work.get("clarifications",[]))' in TEXT
    assert '"question":question' in TEXT
    assert '"reponse_originale"' in TEXT
    assert '"reformulation_proposee"' in TEXT

def test_timeout_real_activity_callback():
    assert 'def mark_user_activity' in TEXT
    assert 'on_change=mark_user_activity' in TEXT
    assert 'update_runtime_activity(event,user_activity=True)' in TEXT
