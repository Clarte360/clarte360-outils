from datetime import datetime, timedelta

from clarte360_pip.framework.config import RGPD_TEXT_VERSION
from clarte360_pip.framework.persistence import (
    build_snapshot,
    infer_resume_page,
    restore_snapshot,
)
from clarte360_pip.framework.rgpd import rgpd_is_current
from clarte360_pip.framework.timeout import is_timed_out


def _base_state():
    return {
        "passation_id": "PIP-B-1",
        "session_id": "S-B-1",
        "navigation_page": "pip_questionnaire",
        "last_useful_page": "pip_questionnaire",
        "journey": "PIP_SEUL",
        "pip_state": {
            "bank_version": "PIP-BANK-0.5",
            "order": ["PIP-ACT-R-R1-001", "PIP-ACT-I-I1-001"],
            "answers": {"PIP-ACT-R-R1-001": 4},
            "index": 1,
        },
        "pip_scoring": {},
        "onet_state": {},
        "feeling": {},
        "session_history": [],
        "rgpd_acceptance": {
            "consentement": True,
            "date": "2026-09-18",
            "heure": "20:00:00",
            "version_texte": RGPD_TEXT_VERSION,
            "study_consent": True,
        },
        "study_consent": True,
        "public_access_verified": True,
        "public_identity": {"first_name": "Test", "last_name": "User"},
        "public_interests": [],
        "public_other_interest": "",
        "public_marketing_opt_in": False,
        "onet_selected_timing": None,
    }


def test_current_rgpd_acceptance_is_recognized_once_per_text_version():
    state = _base_state()
    assert rgpd_is_current(state)
    state["rgpd_acceptance"]["version_texte"] = "ancienne-version"
    assert not rgpd_is_current(state)


def test_rgpd_acceptance_round_trips_in_snapshot():
    state = _base_state()
    payload = build_snapshot(state)
    restored = {}
    restore_snapshot(payload, restored)
    assert restored["rgpd_acceptance"] == state["rgpd_acceptance"]
    assert restored["study_consent"] is True


def test_timeout_snapshot_never_restores_timeout_page():
    state = _base_state()
    state["navigation_page"] = "timeout"
    payload = build_snapshot(state)
    assert payload["navigation_page"] == "pip_questionnaire"
    assert payload["last_useful_page"] == "pip_questionnaire"

    restored = {}
    restore_snapshot(payload, restored)
    assert restored["navigation_page"] == "pip_questionnaire"
    assert restored["pip_state"]["answers"] == {"PIP-ACT-R-R1-001": 4}
    assert "last_activity_at" in restored
    assert restored.get("timeout_at") is None


def test_legacy_timeout_snapshot_is_repaired_on_restore():
    payload = build_snapshot(_base_state())
    payload["navigation_page"] = "timeout"
    payload.pop("last_useful_page", None)
    restored = {}
    restore_snapshot(payload, restored)
    assert restored["navigation_page"] == "pip_questionnaire"


def test_infer_resume_page_does_not_restart_existing_pip():
    state = _base_state()
    state["navigation_page"] = "accueil"
    assert infer_resume_page(state) == "pip_questionnaire"


def test_infer_resume_page_keeps_onet_choice_and_progress():
    state = _base_state()
    state["journey"] = "PIP_PUIS_ONET60"
    state["pip_state"]["completed"] = True
    state["onet_selected_timing"] = "PRE_PIP"
    assert infer_resume_page(state) == "onet_intro"

    state["onet_state"] = {
        "questions": [{"index": i, "text": f"Q{i}"} for i in range(1, 61)],
        "answers": {"1": 3},
        "index": 1,
        "completed": False,
    }
    assert infer_resume_page(state) == "onet_questionnaire"


def test_timeout_boundary_and_activity_reset_contract():
    now = datetime(2026, 9, 18, 20, 0, 0)
    assert is_timed_out((now - timedelta(minutes=16)).isoformat(), now=now, limit_minutes=15)
    assert not is_timed_out((now - timedelta(minutes=14)).isoformat(), now=now, limit_minutes=15)


def test_timeout_message_and_button_match_cdc():
    text = open("clarte360_pip/ui/pages.py", encoding="utf-8").read()
    assert "Votre session a été interrompue pour inactivité. Votre travail n’est pas perdu." in text
    assert "Ne fermez pas cette fenêtre avant d’avoir téléchargé votre sauvegarde de reprise." in text
    assert "TÉLÉCHARGER MA SAUVEGARDE AVANT DE QUITTER" in text
    assert "Un seul téléchargement suffit" in text


def test_home_requires_rgpd_before_public_identity_and_no_120_copy():
    text = open("clarte360_pip/ui/pages.py", encoding="utf-8").read()
    assert 'if not rgpd_is_current(st.session_state):' in text
    assert 'Lire les informations RGPD' in text
    assert "72 activités professionnelles" in text
    assert "120 situations" not in text
