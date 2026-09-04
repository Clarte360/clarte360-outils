from pathlib import Path

TEXT=Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")

def test_version_f3():
    assert 'APP_VERSION = "2.2.0-preproduction-5"' in TEXT

def test_definition_requires_explicit_validation():
    assert 'Valider la définition retenue' in TEXT
    assert 'if not definition_confirmed:' in TEXT
    assert 'Comment souhaitez-vous traiter votre définition ?' in TEXT
    for label in [
        'Conserver ma définition personnelle',
        'Adopter la définition Clarté360',
        'Créer une formulation combinée',
        'Modifier manuellement ma définition',
    ]:
        assert label in TEXT

def test_prerequisite_runs_specific_questionnaire_value_by_value():
    start=TEXT.index('def render_module_1')
    end=TEXT.index('def _hydrate_module2_answers')
    fn=TEXT[start:end]
    assert 'valeur validée en séance — {idx+1} sur {total}' in fn
    assert 'Questionnaire spécifique HEC' in fn
    assert 'm1_q1_' in fn and 'm1_q2_' in fn and 'm1_q3_' in fn
    assert '_upsert_central_value' in fn
    assert 'module1_index=idx+1' in fn
