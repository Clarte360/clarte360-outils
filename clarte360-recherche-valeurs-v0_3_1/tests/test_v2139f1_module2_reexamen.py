from pathlib import Path
TEXT=Path("app.py").read_text(encoding="utf-8")

def test_module2_first_and_existing_answers_use_same_large_question_widget():
    fn=TEXT[TEXT.index("def render_module_2"):TEXT.index("def _module3_current_work")]
    assert fn.count("open_response_widget(") >= 2
    assert "_m2_chat_bubble" not in fn
    assert "allow_reformulation=True" in fn

def test_reexamen_recognized_value_never_blocked_by_definition():
    fn=TEXT[TEXT.index("def render_module_3"):TEXT.index("def _advance_module3")]
    assert 'direct_to_questionnaire = work.get("source")=="reexamen"' in fn
    assert '"decision":"valeur_reconnue"' in fn
    assert "ne peut jamais bloquer le questionnaire spécifique" in fn
    assert "Le questionnaire spécifique est donc bloqué" not in fn

def test_nonvalue_message_is_not_red_or_punitive():
    fn=TEXT[TEXT.index("def render_module_3"):TEXT.index("def _advance_module3")]
    branch=fn[fn.index('if decision=="formulation_non_valeur"'):fn.index('if decision=="valeur_absente_possible"')]
    assert "st.warning" in branch
    assert "st.error" not in branch
