from pathlib import Path

from clarte360_pip.framework.persistence import build_snapshot, restore_snapshot, infer_resume_page


def test_h33a_public_home_exposes_new_and_resume_paths():
    text = Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")
    assert "Commencer une nouvelle passation" in text
    assert "Reprendre une passation déjà commencée" in text
    assert 'key="home_resume_json"' in text
    assert "La reprise est automatique après sélection" in text


def test_h33a_access_code_is_gated_by_two_mandatory_consents_and_marketing_is_not_in_gate():
    text = Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")
    gate = text[text.index("mandatory_consents_ok = bool("):text.index('if st.button("Recevoir mon code d’accès"')]
    assert 'acceptance.get("consentement") is True' in gate
    assert 'acceptance.get("study_consent") is True' in gate
    assert 'st.session_state.get("study_consent") is True' in gate
    assert "marketing" not in gate.lower()
    assert "disabled=not mandatory_consents_ok" in text


def test_h33a_rgpd_public_requires_study_consent_but_accompaniment_logic_remains_separate():
    text = Path("clarte360_pip/framework/rgpd.py").read_text(encoding="utf-8")
    assert "required_ok = bool(accepted and (study if is_public else True))" in text
    assert "deux consentements obligatoires avant l’envoi du code d’accès" in text


def test_h33a_snapshot_keeps_study_id_and_exact_question_on_restore():
    state = {
        "passation_id": "pass-123", "session_id": "sess-123", "journey": "PIP_SEUL",
        "public_access_verified": True, "public_study_id": "study-stable-123",
        "study_consent": True,
        "rgpd_acceptance": {"consentement": True, "study_consent": True, "version_texte": "x"},
        "pip_state": {"order": [f"Q{i:02d}" for i in range(1, 73)], "answers": {"Q01": 3, "Q02": 4}, "index": 2},
        "pip_scoring": {}, "onet_state": {}, "feeling": {}, "session_history": [], "report_documents": [],
        "navigation_page": "pip_questionnaire", "last_useful_page": "pip_questionnaire",
    }
    snap = build_snapshot(state)
    restored = {}
    restore_snapshot(snap, restored)
    assert restored["public_study_id"] == "study-stable-123"
    assert restored["pip_state"]["index"] == 2
    assert infer_resume_page(restored) == "pip_questionnaire"
