from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'app.py'
TEXT = APP.read_text(encoding='utf-8')


def test_version_219a():
    assert 'APP_VERSION = "2.2.0-preproduction"' in TEXT


def test_questionnaire_hec_mentions_value_three_times():
    assert 'Pour vous, la valeur « {value_label} » est-elle importante ?' in TEXT
    assert 'Pour vous, la valeur « {value_label} » est-elle très importante ?' in TEXT
    assert 'Pour vous, la valeur « {value_label} » est-elle fondamentale ?' in TEXT


def test_definition_ai_rewrite_removed():
    assert 'Demander une reformulation Clarté360' not in TEXT[TEXT.index('def _value_definition_choices'):TEXT.index('def render_modules_home')]


def test_module4_checkpoint_and_module2_gate():
    assert 'checkpoint_hypotheses' in TEXT
    assert 'Une autre valeur vous est-elle venue à l’esprit ?' in TEXT
    assert 'La voie 2 utilise les réponses du Module 2' in TEXT
    assert 'len(exchanges)>=3' in TEXT


def test_json_spinner():
    assert 'Préparation de votre sauvegarde JSON…' in TEXT
