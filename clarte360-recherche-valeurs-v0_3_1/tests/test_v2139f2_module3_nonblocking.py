from pathlib import Path

TEXT=Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")

def _module3():
    return TEXT[TEXT.index("def render_module_3"):TEXT.index("def _advance_module3")]

def test_version_9f2():
    assert 'APP_VERSION = "2.1.3.9F2-preproduction"' in TEXT

def test_non_value_analysis_never_blocks_module3():
    fn=_module3()
    branch=fn[fn.index('if decision=="formulation_non_valeur"'):fn.index('elif decision=="valeur_absente_possible"')]
    assert "return" not in branch
    assert "Elle ne bloque jamais votre parcours" in branch
    assert "Questionnaire spécifique Clarté360" in fn

def test_reexamen_goes_directly_to_definition_and_questionnaire():
    fn=_module3()
    assert 'direct_to_questionnaire = work.get("source")=="reexamen"' in fn
    assert 'if not direct_to_questionnaire:' in fn
    assert fn.index('choice,final_def=_value_definition_choices') < fn.index('Questionnaire spécifique Clarté360')

def test_absent_value_can_receive_ai_definition():
    assert 'definition_proposee' in TEXT
    assert 'Définition proposée par Clarté360' in TEXT
