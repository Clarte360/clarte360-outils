from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "app.py").read_text(encoding="utf-8")


def test_version_is_ux_navigation_release():
    assert 'APP_VERSION = "1.8.6-ux-navigation-retour-audio"' in SRC


def test_sidebar_branding_and_question_navigation_present():
    assert 'st.sidebar.image(str(LOGO_PATH), width=72)' in SRC
    assert '"← Question précédente"' in SRC
    assert '"Valider et continuer →"' in SRC


def test_previous_navigation_never_deletes_validated_positions():
    start = SRC.index('if previous_clicked:')
    end = SRC.index('if validate_clicked:', start)
    block = SRC[start:end]
    assert 'st.session_state.current_index = max(0, idx - 1)' in block
    assert 'positions.pop' not in block
    assert 'st.session_state.positions.pop' not in block
    assert 'del st.session_state.positions' not in block


def test_audio_controls_are_compact_and_do_not_require_streamlit_rerun():
    start = SRC.index('def speak_button')
    end = SRC.index('def display_header', start)
    block = SRC[start:end]
    assert 'speechSynthesis.speak' in block
    assert 'speechSynthesis.cancel' in block
    assert 'Écouter la question' in block
    assert 'st.button(' not in block


def test_guard_scans_all_rendered_slider_drafts_after_back_navigation():
    start = SRC.index('def current_business_fingerprint')
    end = SRC.index('def mark_json_downloaded', start)
    block = SRC[start:end]
    assert 'slider_drafts' in block
    assert 'sorted(drafts.items()' in block
    assert 'draft_slider=draft_sliders or None' in block


def test_questionnaire_business_source_untouched_by_ux_release():
    import hashlib
    data = (ROOT / 'data' / 'moteurs_professionnels_curseurs_v0_1.xlsx').read_bytes()
    assert hashlib.sha256(data).hexdigest() == '59ccff89ded080d141a58b9c31a1fc290a7236daffaa9d84629c3446487f31b3'



def test_question_screen_persists_unvalidated_draft_outside_widget_state():
    start = SRC.index('def questionnaire_screen')
    end = SRC.index('def results_screen', start)
    block = SRC[start:end]
    assert 'drafts = st.session_state.setdefault("slider_drafts", {})' in block
    assert 'default_pos = int(drafts.get(cid, baseline_pos))' in block
    assert 'drafts[cid] = int(pos)' in block
    assert 'st.session_state.slider_drafts.pop(cid, None)' in block
