from pathlib import Path
import ast

APP = Path(__file__).resolve().parents[1] / "app.py"
SRC = APP.read_text(encoding="utf-8")


def test_preproduction4_declared_and_compiles():
    assert 'APP_VERSION = "2.2.0-preproduction-4"' in SRC
    ast.parse(SRC)


def test_five_question_hard_stop_goes_to_global_review_not_sixth_question():
    assert 'if _module4_vertical_count(cycle)>=MODULE4_MAX_VERTICAL_QUESTIONS:' in SRC
    assert 'cycle["stage"]="synthese_globale_pending"' in SRC
    assert 'cycle["review_trigger"]="limite_cinq_questions"' in SRC
    assert 'aucune sixième question automatique' in SRC


def test_global_review_uses_all_module4_memory_and_known_values():
    assert 'def _module4_memory_exchanges' in SRC
    assert 'module4_question_memory' in SRC
    assert 'def _module4_active_known_items' in SRC
    assert 'central_validated_values' in SRC
    assert 'values_to_examine' in SRC
    assert 'hypothesis_basket' in SRC
    assert 'def _module4_global_review' in SRC
    assert 'Relisez TOUS les couples questions-réponses validés' in SRC
    assert 'au moins deux situations différentes' in SRC


def test_user_can_request_review_and_choose_next_route():
    assert 'Faire le point avec mes réponses actuelles' in SRC
    assert 'Explorer avec l’autre voie' in SRC
    assert 'Continuer avec 5 nouvelles questions maximum' in SRC
    assert 'Arrêter pour le moment' in SRC


def test_followups_stay_on_same_thread():
    assert 'Restez impérativement dans la situation, le récit ou le fil immédiatement en cours.' in SRC
    assert 'Ne changez pas de domaine de vie' in SRC
