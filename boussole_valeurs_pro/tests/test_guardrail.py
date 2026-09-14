from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

def test_version_guardrail():
    assert '1.8.4-validation-saisies-vps-hub-ready-garde-fou' in SRC

def test_beforeunload_present():
    assert 'onbeforeunload' in SRC

def test_input_and_change_rearm():
    assert "addEventListener('input', markDirty" in SRC
    assert "addEventListener('change', markDirty" in SRC

def test_fingerprint_present():
    assert 'def current_work_fingerprint' in SRC
    assert 'saved_work_fingerprint' in SRC

def test_json_download_marks_clean():
    assert 'def mark_json_downloaded' in SRC
    assert 'mark_current_work_saved()' in SRC

def test_json_exports_use_callback():
    assert SRC.count('on_click=mark_json_downloaded') >= 3

def test_import_sets_clean_baseline():
    marker = 'st.session_state.saved_work_fingerprint = current_work_fingerprint(st.session_state.data)'
    assert SRC.count(marker) >= 2
