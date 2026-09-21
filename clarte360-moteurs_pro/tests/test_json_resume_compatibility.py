import ast
import json
from pathlib import Path

from validation import decode_progress_bytes


def legacy_cloud_payload():
    # Structure représentative d'un JSON V1.8.0 Streamlit Cloud, anonymisée.
    return {
        "outil": "clarte360_moteurs_professionnels",
        "app_version": "1.8.0-socle-clarte360",
        "passation_root_id": "d6acf88e-d666-4938-aceb-e9cb6e6e1da4",
        "session_id": "e3bd9743-fa8d-422a-bdbe-ad37686f7a97",
        "passation_id": "CL360-MP-20260917-123142-E3BD9743",
        "beneficiaire": {
            "nom": "Dupont",
            "prenom": "Camille",
            "email": "camille.dupont@example.org",
            "consultant": "Consultant Clarte360",
        },
        "cursor_order_displayed": ["C001", "C002", "C003"],
        "positions": {"C001": 5, "C002": 0, "C003": 10},
        "code_verified_at": "2026-09-17T12:31:42",
        "rgpd_acceptance": {"consentement": True, "version_texte": "RGPD-Clarte360-v1.0-2026-07"},
        "access_history": {
            "validation_code": {
                "date_heure": "2026-09-17T12:31:42",
                "code_valide": True,
                "version_application": "1.8.0-socle-clarte360",
            }
        },
        "sessions": [],
    }


def test_legacy_cloud_180_json_decodes_with_current_cursor_reference():
    payload = legacy_cloud_payload()
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    restored = decode_progress_bytes(raw, ["C001", "C002", "C003"])
    assert restored["app_version"] == "1.8.0-socle-clarte360"
    assert restored["access_history"]["validation_code"]["code_valide"] is True
    assert restored["positions"] == {"C001": 5, "C002": 0, "C003": 10}


def test_import_screen_receives_active_reference_and_main_passes_it():
    source = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    f = funcs["import_json_screen"]
    assert [a.arg for a in f.args.args] == ["active"]

    calls = [n for n in ast.walk(funcs["main"]) if isinstance(n, ast.Call)]
    matching = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "import_json_screen"]
    assert len(matching) == 1
    assert len(matching[0].args) == 1 and isinstance(matching[0].args[0], ast.Name) and matching[0].args[0].id == "active"


def test_restore_logic_marks_code_as_already_verified_on_json_resume():
    source = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    segment = ast.get_source_segment(source, funcs["restore_from_progress"]) or ""
    assert "st.session_state.code_verified = True" in segment
    assert 'init_runtime_session("reprise_depuis_json")' in segment
