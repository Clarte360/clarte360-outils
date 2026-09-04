from pathlib import Path

TEXT = Path('app.py').read_text(encoding='utf-8')

def test_version_219b():
    assert 'APP_VERSION = "2.2.0-preproduction-4"' in TEXT

def test_original_always_visible_for_light_corrections():
    assert '<b>Transcription initiale</b>' in TEXT
    assert '<b>Réponse initiale</b>' in TEXT
    assert 'Comparez les deux versions avant de choisir.' in TEXT

def test_single_click_internal_retry():
    assert 'def reliable_clean_spoken_text' in TEXT
    assert 'for attempt in range(2)' in TEXT
    assert 'return _expression_result("echec_technique"' in TEXT

def test_module_reentry_and_abandon_cleanup():
    assert 'def _module_has_temporary_work' in TEXT
    assert 'def _abandon_module_temporary_work' in TEXT
    assert "Abandonner ce travail et revenir au menu du module" in TEXT

def test_json_preparation_spinner():
    assert 'Préparer ma sauvegarde JSON' in TEXT
    assert 'Préparation de votre fichier…' in TEXT
