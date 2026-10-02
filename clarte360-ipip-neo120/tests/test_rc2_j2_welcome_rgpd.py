from pathlib import Path
from types import SimpleNamespace

from clarte360_ipip.framework.config import RGPD_TEXT_VERSION
from clarte360_ipip.framework.rgpd import (
    NON_CLINICAL_NOTICE,
    build_information_record,
    information_is_current,
)
from clarte360_ipip.version import APP_VERSION


def test_j2_rgpd_text_version_is_final_for_j2():
    assert RGPD_TEXT_VERSION == "RGPD-Clarte360-IPIP-v1.6-J2-20261001"


def test_j2_information_trace_contains_required_fields():
    ctx = SimpleNamespace(
        prescription_id="PRESC-1",
        beneficiary_id="BEN-1",
        action_id="ACT-1",
        participant_id="PART-1",
    )
    record = build_information_record(ctx=ctx, reference_version="IPIP-FR-V1.0", understood=True, proceed=True)
    for key in [
        "text_version", "recorded_at", "prescription_id", "app_version", "reference_version",
        "information_read", "understanding_confirmed", "passation_requested",
    ]:
        assert key in record
    assert record["text_version"] == RGPD_TEXT_VERSION
    assert record["app_version"] == APP_VERSION
    assert information_is_current(record, "IPIP-FR-V1.0")


def test_j2_information_trace_rejects_outdated_text_or_reference():
    ctx = SimpleNamespace(prescription_id="P", beneficiary_id="B", action_id="A", participant_id=None)
    record = build_information_record(ctx=ctx, reference_version="REF-1", understood=True, proceed=True)
    assert not information_is_current({**record, "text_version": "old"}, "REF-1")
    assert not information_is_current(record, "REF-2")
    assert not information_is_current({**record, "understanding_confirmed": False}, "REF-1")


def test_j2_non_clinical_notice_matches_cdc_guardrail():
    assert "tendances de fonctionnement" in NON_CLINICAL_NOTICE
    assert "évaluation clinique" in NON_CLINICAL_NOTICE
    assert "diagnostic psychologique ou psychiatrique" in NON_CLINICAL_NOTICE
    assert "valeurs" in NON_CLINICAL_NOTICE and "motivations" in NON_CLINICAL_NOTICE


def test_j2_home_contains_required_experience_elements():
    src = Path("clarte360_ipip/ui/pages.py").read_text(encoding="utf-8")
    for label in [
        "Profil de fonctionnement professionnel", "Explorer mes tendances de fonctionnement",
        "120", "Sauvegarde", "Reprise", "ni un diagnostic", "ni une mesure d'intelligence",
        "ni une recommandation automatique de métier",
    ]:
        assert label in src


def test_j2_rgpd_is_specific_to_ipip_and_not_fake_consent():
    src = Path("clarte360_ipip/framework/rgpd.py").read_text(encoding="utf-8")
    for label in [
        "120 affirmations", "scores calculés", "rapport final", "questionnaire de ressenti",
        "réponses brutes", "aucune décision automatisée", "Vos droits", "consentement RGPD",
    ]:
        assert label in src
    assert "consentement_rgpd" not in src.lower()


def test_j2_app_blocks_passation_until_information_current():
    src = Path("app.py").read_text(encoding="utf-8")
    assert "if page=='passation' and not info_current:" in src
    assert "save_information_record" in src
    assert "information_is_current" in src
    assert "render_rgpd_information(show_confirmation=True" in src


def test_j2_mentions_o6_and_french_adaptation_limit():
    src = Path("clarte360_ipip/ui/pages.py").read_text(encoding="utf-8")
    assert "Ouverture aux conventions" in src
    assert "validation psychométrique française indépendante" in src
