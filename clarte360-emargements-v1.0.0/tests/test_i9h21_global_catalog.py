from pathlib import Path

def test_tools_are_global_not_action_assigned():
    src=Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
    assert "catalogue global Clarté360" in src
    assert "CRÉER L’IDENTITÉ PERMANENTE + ENVOYER L’INVITATION" in src
    assert "tool_action" not in Path(__file__).resolve().parents[1].joinpath("db.py").read_text(encoding="utf-8")

def test_admin_tools_tab_can_create_or_link_identity():
    src=Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
    assert "create_beneficiary_from_participant" in src
    assert "link_participant_to_beneficiary" in src
    assert "find_beneficiary_candidates" in src
