from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

def test_sidebar_json_is_never_served_from_cached_bytes():
    assert 'data=st.session_state.get("exit_json_bytes"' not in SRC
    assert 'current_json_bytes = json_snapshot_bytes(current_data)' in SRC
    assert 'for key in ("exit_json_bytes", "exit_json_filename", "exit_json_fingerprint")' in SRC

def test_json_download_is_bound_to_rendered_fingerprint():
    assert 'args=(current_json_fingerprint,)' in SRC
    assert SRC.count('args=(business_state_fingerprint(data),)') >= 3
    assert 'export_fingerprint != current' in SRC

def test_all_json_outputs_use_single_serializer():
    assert SRC.count('json_snapshot_bytes(data)') >= 3
    assert 'st.session_state.exit_json_bytes = json.dumps' not in SRC
