from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_teams_duration_helper_is_explicitly_imported():
    text=(ROOT/"app.py").read_text(encoding="utf-8")
    assert "from services import _duration_hms" in text

def test_teams_admin_uses_local_times_and_exact_duration():
    text=(ROOT/"app.py").read_text(encoding="utf-8")
    assert "Début réel" in text
    assert "Fin réelle" in text
    assert "Durée réunion" in text
    assert "Rapprochement Clarté360" in text
