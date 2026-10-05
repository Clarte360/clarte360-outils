from pathlib import Path

from guard_state import fingerprint, persisted_fingerprint, is_dirty


def test_sidebar_has_logo_and_question_navigation():
    src = Path("app.py").read_text(encoding="utf-8")
    assert 'st.image(str(LOGO_PATH), width=88)' in src
    assert 'Questionnaire : {idx + 1} / {total}' in src


def test_intro_blocks_are_conditioned_before_passation():
    src = Path("app.py").read_text(encoding="utf-8")
    expected = 'if not st.session_state.get("test_started"):\n    st.markdown(\n        """\n        <div class="objectif-box">'
    assert expected in src


def test_previous_navigation_preserves_answers_and_preselects_saved_answer():
    src = Path("app.py").read_text(encoding="utf-8")
    pos = src.index('← Question précédente')
    window = src[pos-700:pos+900]
    assert 'st.session_state.current_index = previous_question_index(idx)' in window
    assert 'st.session_state.answers.pop' not in window
    assert 'saved_opt = st.session_state.answers.get(qid)' in src
    assert 'index=answer_index_for_options(saved_opt, options)' in src
    assert 'format_func=lambda opt: labels[opt]' in src


def test_preselected_validated_radio_does_not_rearm_guard():
    state = {
        "test_started": True,
        "beneficiaire": {"nom": "Dupont", "prenom": "Anne", "email": "anne@example.fr"},
        "answers": {"Q001": "A"},
        "current_index": 0,
        "question_order": ["Q001", "Q002"],
        "option_orders": {"Q001": ["A", "B", "C", "D"], "Q002": ["A", "B", "C", "D"]},
        "radio_Q001": "A",
    }
    saved = persisted_fingerprint(state)
    assert fingerprint(state) == saved
    assert is_dirty(state, saved) is False


def test_changed_preselected_radio_rearms_guard_until_validation():
    state = {
        "test_started": True,
        "beneficiaire": {"nom": "Dupont", "prenom": "Anne", "email": "anne@example.fr"},
        "answers": {"Q001": "A"},
        "current_index": 0,
        "question_order": ["Q001", "Q002"],
        "option_orders": {"Q001": ["A", "B", "C", "D"], "Q002": ["A", "B", "C", "D"]},
        "radio_Q001": "B",
    }
    saved = persisted_fingerprint({**state, "radio_Q001": "A"})
    assert is_dirty(state, saved) is True
