from pathlib import Path
TEXT=(Path(__file__).parents[1]/'app.py').read_text(encoding='utf-8')

def test_version_9d_and_clarification_tracks():
    assert 'APP_VERSION = "2.1.3.9F-preproduction"' in TEXT
    assert 'clarification_tracks' in TEXT
    assert 'Envoyer vers Pistes à clarifier' in TEXT
    assert 'piste_clarifier' in TEXT

def test_module3_blocks_need_fear_and_module4_has_verticality():
    assert 'le nom de la valeur est prioritaire' in TEXT
    assert 'Le questionnaire spécifique est donc bloqué' in TEXT
    assert 'entre trois et cinq relances utiles' in TEXT
    assert 'ce qui était le plus important pour vous dans cette situation' in TEXT

def test_no_specific_questionnaire_in_module4_hypothesis_flow():
    assert 'cycle["result"]="hypothese_retenue"' in TEXT
    assert 'st.session_state.hypothesis_basket.append(item)' in TEXT
