from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

def test_version_guardrail():
    assert '1.8.5-vps-mail-hub-registry' in SRC

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


def test_v185_vps_mail_hub_production_wiring():
    from pathlib import Path
    import json
    root=Path(__file__).resolve().parents[1]
    src=(root/'app.py').read_text(encoding='utf-8')
    assert 'Mode test : code généré' not in src and 'Mode test : nouveau code généré' not in src
    assert '_secret_section("MAIL", "mail", "email"' in src
    assert 'handle_hub_launch()' in src and 'verify_launch_token' in src
    ident=json.loads((root/'config'/'app_identity.json').read_text(encoding='utf-8'))
    assert ident['deployment_status']=='production' and ident['internal_port']==8505
    service=(root/'deploy'/'clarte360-boussole-valeurs.service.example').read_text(encoding='utf-8')
    assert 'User=ubuntu' in service and '--server.port 8505' in service and 'boussole_valeurs_pro' in service
