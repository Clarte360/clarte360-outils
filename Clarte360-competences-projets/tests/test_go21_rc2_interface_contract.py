from __future__ import annotations

from clarte360_cp.ui.beneficiaire import DOC_LABELS, FRIENDLY_PHASE, PHASE_HELP, _beneficiary_state_label
from clarte360_cp.ui.accompagnateur import _beneficiary_share_state
from clarte360_cp.ui.spec import BENEFICIARY_PAGES


def test_rc2_adds_journey_and_actions_as_primary_beneficiary_spaces():
    assert "b_journey" in BENEFICIARY_PAGES
    assert "b_actions" in BENEFICIARY_PAGES


def test_rc2_all_twelve_stages_have_human_labels_and_explanations():
    assert set(FRIENDLY_PHASE) == set(range(12))
    assert set(PHASE_HELP) == set(range(12))
    assert all("phase" not in FRIENDLY_PHASE[i].lower() for i in range(12))


def test_rc2_phase_zero_is_materialized_as_enriched_professional_journey():
    assert FRIENDLY_PHASE[0] == "Mon parcours professionnel"
    assert DOC_LABELS["PARCOURS_PRO_ENRICHI"] == "Mon parcours professionnel enrichi"
    assert "IA" in PHASE_HELP[0]


def test_rc2_beneficiary_can_understand_states_without_technical_wording():
    assert _beneficiary_state_label("NON_DISPONIBLE") == "Pas encore travaillé"
    assert _beneficiary_state_label("EN_ATTENTE_BENEFICIAIRE") == "À relire / confirmer"
    assert _beneficiary_state_label("VALIDEE") == "Validé"


def test_rc2_accompanist_publication_contract_distinguishes_work_and_shared_result():
    assert _beneficiary_share_state("EN_COURS")[0] == "Non publié"
    assert _beneficiary_share_state("EN_ATTENTE_BENEFICIAIRE")[0] == "Publié au bénéficiaire"
    assert _beneficiary_share_state("VALIDEE")[0] == "Publié et validé"
