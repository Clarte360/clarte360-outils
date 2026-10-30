from __future__ import annotations

import json
from datetime import datetime, timezone

from clarte360_cp.application.rome_matching import (
    add_session_experience, read_career_cards, run_rome_matching_analysis,
    save_rome_matching_review, update_session_experience,
)
from clarte360_cp.connectors.cav3_ai import Cav3AISettings
from clarte360_cp.domain.rome_matching import rome_study_items
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import CareerItem, CareerVersion, ExternalSnapshot, JobTarget, MatchingItem, PhaseState
from clarte360_cp.repositories.beneficiary import BeneficiaryRepository
from tests.helpers import context


class FakeResponses:
    def __init__(self, experience_id):
        self.calls = []
        self.experience_id = experience_id
    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = {"propositions": [{"rome_item_key": "SAVOIR:117781", "statut_propose": "ACQUIS_POTENTIEL",
            "experience_refs": [self.experience_id], "raisonnement": "Suivi concret des comptes clients.",
            "question_en_seance": "Quelles opérations réalisiez-vous ?"}], "incertitudes": []}
        return type("Response", (), {"status": "completed", "output_text": json.dumps(result), "usage": None})()


class FakeClient:
    def __init__(self, experience_id):
        self.responses = FakeResponses(experience_id)


def test_ai_proposal_then_accompanist_review_is_versioned_and_shared(Session, engine):
    ctx = context()
    payload = {"code_rome": "M1203", "intitule": "Comptable", "version": "ROME-4.0-test",
        "competences": {"savoirs": {"categories": [{"libelle": "Expertise", "items": [
            {"libelle": "Comptabilité client", "code_ogr": "117781"}]}]}}}
    with Session() as session:
        case = CaseRepository(session).open_or_create(ctx)
        snapshot = ExternalSnapshot(case_id=case.case_id, provider="FRANCE_TRAVAIL", resource_type="ROME_FICHE_METIER",
            external_key="M1203", payload_json=json.dumps(payload), sha256="a"*64,
            effective_date="2026-10-23")
        session.add(snapshot); session.flush()
        target = JobTarget(case_id=case.case_id, rome_code="M1203", rome_label="Comptable",
            snapshot_id=snapshot.snapshot_id, status="ACTIVE", selected_order=1)
        career = CareerItem(case_id=case.case_id, item_type="EMPLOI", title="Gestionnaire de comptes",
            details_json=json.dumps({"activities": "Suivi des règlements et lettrage des comptes clients."}), status="ACTIVE")
        session.add_all([target, career]); session.commit()
        case_id, target_id, experience_id = case.case_id, target.job_target_id, career.career_item_id

    client = FakeClient(experience_id)
    analysis = run_rome_matching_analysis(ctx, case_id, target_id, ai_settings=Cav3AISettings("synthetic", "synthetic"),
        database_url=str(engine.url), client=client)
    assert analysis["current"] is True
    assert client.responses.calls[0]["store"] is False
    saved = save_rome_matching_review(ctx, case_id, target_id, [{
        "rome_item_key": "SAVOIR:117781", "status": "ACQUIS_ETAYE",
        "experience_ids": [experience_id], "rationale": "Le bénéficiaire décrit le suivi et le lettrage des comptes clients.",
        "exercise_level": 2,
    }], analysis_id=analysis["analysis_id"], database_url=str(engine.url))
    assert saved["version_no"] == 1

    with Session() as session:
        beneficiary = BeneficiaryRepository(session).load(case_id)
    assert len(beneficiary.matching_details) == 1
    detail = beneficiary.matching_details[0]
    assert detail.status == "ACQUIS_ETAYE"
    assert detail.exercise_level == 2
    assert detail.evidence_titles == ("Expérience — Gestionnaire de comptes",)
    assert "lettrage" in detail.rationale

    added_id = add_session_experience(ctx, case_id, title="Études de comptabilité sans diplôme", kind="ETUDE",
                           activities="Étude personnelle du plan comptable et pratique sur des cas.",
                           level_of_exercise=2,
                           database_url=str(engine.url))
    with Session() as session:
        refreshed = BeneficiaryRepository(session).load(case_id)
        added = session.get(CareerItem, added_id)
    assert refreshed.matching_details == ()
    assert added.item_type == "ETUDE"
    added_details = json.loads(added.details_json)
    assert added_details["niveau_exercice"] == 2
    assert added_details["niveau_exercice_source"] == "DISCUTE_EN_SEANCE"

    sourced_id = add_session_experience(ctx, case_id, title="Assistant comptable proposé depuis le CV", kind="EMPLOI",
                           activities="Suivi des factures à confirmer en séance.", source_ref="GDA-CV-17", source_span_ref="CV:GDA-CV-17:1",
                           database_url=str(engine.url))
    with Session() as session:
        sourced = session.get(CareerItem, sourced_id)
    sourced_details = json.loads(sourced.details_json)
    assert sourced.source_span_ref == "CV:GDA-CV-17:1"
    assert sourced_details["provenance"] == "REFERENCE_GDA"
    assert sourced_details["source_ref"] == "GDA-CV-17"
    assert sourced_details["statut_humain"] == "A_CONFIRMER"
    duplicate_id = add_session_experience(ctx, case_id, title="Assistant comptable proposé depuis le CV", kind="EMPLOI",
                           activities="Suivi des factures à confirmer en séance.", source_ref="GDA-CV-17", source_span_ref="CV:GDA-CV-17:1",
                           database_url=str(engine.url))
    assert duplicate_id == sourced_id


def test_rome_xml_concepts_normalize_to_savoir_and_skills():
    payload = {"fiche_metier": {"rome": {"code_rome": "M1203", "intitule": "Comptable"},
        "competences": {"savoirs": {"categories": [{"libelle": "Expertise", "items": [
            {"libelle": "Fiscalité", "code_ogr": "2"}]}]},
            "savoir_faire": {"enjeux": [{"libelle": "Gestion", "items": [
                {"libelle": "Contrôler les comptes", "code_ogr": "1"}]}]}}}}
    items = rome_study_items(payload)
    assert {x.category for x in items} == {"SAVOIR", "SAVOIR_FAIRE"}


def test_career_card_session_review_is_versioned_and_invalidates_rome_review(Session, engine):
    coach = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        session.query(PhaseState).filter_by(case_id=case.case_id, phase_no=0).one().state = "VALIDEE"
        session.query(PhaseState).filter_by(case_id=case.case_id, phase_no=3).one().state = "VALIDEE"
        snapshot = ExternalSnapshot(case_id=case.case_id, provider="FRANCE_TRAVAIL", resource_type="ROME_FICHE_METIER",
            external_key="M1203", payload_json="{}", sha256="b" * 64, effective_date="2026-10-23")
        session.add(snapshot); session.flush()
        target = JobTarget(case_id=case.case_id, rome_code="M1203", rome_label="Comptable",
            snapshot_id=snapshot.snapshot_id, status="ACTIVE", selected_order=1)
        session.add(target); session.flush()
        career = CareerItem(case_id=case.case_id, item_type="EMPLOI", title="Aide-comptable",
            details_json=json.dumps({"activities": "Saisie comptable", "provenance": "REFERENCE_GDA"}),
            source_span_ref="APPORT_SEANCE", status="ACTIVE")
        match = MatchingItem(case_id=case.case_id, job_target_id=target.job_target_id, rome_item_key="SAVOIR:test",
            category="SAVOIR", rome_label="Comptabilité", version_no=1,
            proposed_status="ACQUIS_POTENTIEL", final_status="ACQUIS_ETAYE", review_required=0)
        session.add_all([career, match]); session.commit()
        case_id, career_id, matching_id = case.case_id, career.career_item_id, match.matching_id

    update_session_experience(coach, case_id, career_id, title="Aide-comptable confirmé", kind="EMPLOI",
        activities="Saisie et contrôle des écritures ; rapprochements bancaires.",
        autonomy="Réalise les rapprochements en autonomie.", level_of_exercise=2,
        beneficiary_reviewed=True, database_url=str(engine.url))
    cards = read_career_cards(coach, case_id, database_url=str(engine.url))
    assert cards[0]["source_linked"] is False  # APPORT_SEANCE is not a GDA document reference.
    assert cards[0]["details"]["provenance"] == "REFERENCE_GDA"
    assert cards[0]["details"]["statut_humain"] == "RELUE_EN_SEANCE"
    with Session() as session:
        assert session.get(MatchingItem, matching_id).review_required == 1
        versions = session.query(CareerVersion).filter_by(case_id=case_id).all()
        assert len(versions) == 1
        snapshot = json.loads(versions[0].summary_json)
        assert snapshot["title"] == "Aide-comptable confirmé"
        assert snapshot["details"]["niveau_exercice"] == 2
        assert session.query(PhaseState).filter_by(case_id=case_id, phase_no=0).one().state == "REOUVERTE"
        assert session.query(PhaseState).filter_by(case_id=case_id, phase_no=3).one().state == "REOUVERTE"
        assert BeneficiaryRepository(session).load(case_id).career_items == ()
