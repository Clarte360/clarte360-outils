from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app.py"
TEXT = APP.read_text(encoding="utf-8")


def test_8c_version_and_removed_useless_accompanist_review():
    assert 'APP_VERSION = "2.1.3.9F4-preproduction"' in TEXT
    assert "Je souhaite revoir cette valeur avec mon accompagnateur" not in TEXT


def test_module2_shows_all_questions_and_hydrates_legacy_answers():
    assert "def _hydrate_module2_answers" in TEXT
    assert "for q in MODULE2_QUESTIONS[:idx]" in TEXT
    assert "Vos réponses sont enregistrées. Vous pouvez modifier chacune d’elles à tout moment" in TEXT


def test_module3_pending_preview_and_safe_exit():
    assert "def _pending_value_summary" in TEXT
    assert "Poursuivre l’examen de cette valeur" in TEXT
    assert "Retour sans modifier" in TEXT
    assert "Quitter sans modifier" not in TEXT
    assert "Abandonner la valeur en cours" in TEXT
    assert "Arrêter la saisie des valeurs restantes" in TEXT


def test_reexamination_warning_and_cancel():
    assert "répondre de nouveau au questionnaire spécifique" in TEXT
    assert "def _cancel_module3_work" in TEXT
    assert "Commencer le réexamen" in TEXT


def test_navigation_has_centered_professional_css():
    assert 'section[data-testid="stSidebar"] div[data-testid="stButton"] > button' in TEXT
    assert "text-align:center" in TEXT
