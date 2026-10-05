from pathlib import Path

from guard_state import fingerprint, is_dirty, persisted_fingerprint


def _state():
    return {
        "test_started": True,
        "beneficiaire": {"nom": "Dupont", "prenom": "Anne", "email": "anne@example.fr"},
        "answers": {"Q001": "A"},
        "current_index": 1,
        "question_order": ["Q001", "Q002"],
        "option_orders": {"Q001": ["A", "B", "C", "D"], "Q002": ["A", "B", "C", "D"]},
    }


def test_persisted_fingerprint_matches_json_state_only():
    state = _state()
    saved = persisted_fingerprint(state)
    assert is_dirty(state, saved) is False


def test_unvalidated_radio_is_not_claimed_as_saved_by_json():
    state = _state()
    state["radio_Q002"] = "Une réponse sélectionnée mais non validée"
    saved = persisted_fingerprint(state)
    assert fingerprint(state) != saved
    assert is_dirty(state, saved) is True


def test_validated_answer_rearms_guard_after_previous_json():
    state = _state()
    saved = persisted_fingerprint(state)
    state["answers"]["Q002"] = "C"
    state["current_index"] = 2
    assert is_dirty(state, saved) is True


def test_sidebar_json_is_rebuilt_instead_of_cached():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "exit_json_payload = build_progress_json()" not in source
    assert "current_json_bytes = json_download_bytes(build_progress_json())" in source
    assert "current_json_fingerprint = guard_persisted_fingerprint(st.session_state)" in source
    assert "args=(current_json_fingerprint,)" in source


def test_quit_mode_uses_prepared_exit_screen():
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'st.session_state.exit_mode = "quit"' in source
    assert 'st.session_state.get("exit_mode") == "quit"' in source
    assert "Votre JSON de sortie est prêt à être téléchargé" in source
