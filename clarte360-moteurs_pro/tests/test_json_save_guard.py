from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


def test_sidebar_never_serves_cached_json_bytes():
    assert 'data=st.session_state.get("exit_json_bytes"' not in SRC
    assert 'current_json_bytes = payload_bytes(current_payload)' in SRC
    assert 'current_payload = build_payload(active, dims, params, completed=False)' in SRC


def test_preparation_invalidates_any_old_cached_copy():
    assert 'for key in ("exit_json_bytes", "exit_json_filename", "exit_json_fingerprint")' in SRC
    assert 'st.session_state.exit_json_prefix = filename_prefix' in SRC


def test_downloads_are_bound_to_rendered_business_fingerprint():
    assert 'args=(current_json_fingerprint,)' in SRC
    assert SRC.count('args=(persisted_business_fingerprint(),)') >= 2
    assert 'def mark_json_downloaded(export_fingerprint: str | None = None):' in SRC
    assert 'st.session_state.guard_saved_fingerprint = export_fingerprint or persisted_business_fingerprint()' in SRC


def test_json_fix_remains_present_in_current_release():
    assert 'APP_VERSION = "1.8.6-ux-navigation-retour-audio"' in SRC
