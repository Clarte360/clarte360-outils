from __future__ import annotations

from datetime import date

import pytest

from clarte360_cp.application.conclusion import (
    close_bilan, finalize_synthesis, read_conclusion, respond_to_conclusion,
    save_followup_plan, save_results, save_synthesis, submit_followup_response,
)
from clarte360_cp.application.go23 import CRITERIA, publish_project_decision, record_project_decision, save_comparison
from clarte360_cp.application.go24 import save_action_plan
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import FollowUpPlan, JobTarget
from tests.helpers import context


def _contexts_and_case(Session, database_url):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_PUBLISH"])
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_VALIDATE"], actor="BEN-1")
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        target = JobTarget(case_id=case.case_id, rome_code="M1203", rome_label="Comptable", status="ACTIVE")
        session.add(target); session.commit()
        case_id, target_id = case.case_id, target.job_target_id
    save_comparison(coach, case_id, [{"job_target_id": target_id, "criterion": criterion,
        "content": "À vérifier avec une source datée avant de tirer une conclusion."} for criterion in CRITERIA],
        publish=True, database_url=database_url)
    decision_id = record_project_decision(coach, case_id, job_target_id=target_id, decision_type="PRIORITAIRE",
        wording="Le bénéficiaire choisit ce projet après comparaison de ses acquis et conditions de réalisation.",
        database_url=database_url)
    publish_project_decision(coach, case_id, decision_id=decision_id, database_url=database_url)
    save_action_plan(coach, case_id, [{"action": "Réaliser deux entretiens avec des professionnels"}],
        publish=True, database_url=database_url)
    return coach, beneficiary, case_id


def _six_month_date():
    today = date.today()
    month = today.month + 6
    year = today.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return date(year, month, min(today.day, 28)).isoformat()


def _results():
    return {
        "parcours": "Expériences de gestion et de suivi comptable, détaillées avec le bénéficiaire.",
        "savoirs": "Clôture périodique et contrôle des pièces, étayés par plusieurs expériences.",
        "projet": "Projet de comptable confirmé par le bénéficiaire après comparaison.",
        "conditions": "Vérifier les horaires de clôture et le niveau d'autonomie attendu.",
        "vigilances": "Le périmètre de responsabilité en entreprise reste à préciser.",
        "formations": "Aucune formation obligatoire identifiée; compléter les outils de gestion si souhaité.",
        "diploma_status": "Aucune obligation de diplôme confirmée pour ce poste.",
        "diploma_source": "Non applicable à ce poste; confirmer selon l'activité réglementée exacte.",
    }


def _synthesis():
    return {"objectif": "Étudier la faisabilité d'une évolution vers un poste de comptable.",
            "projet": "Le bénéficiaire retient un poste de comptable en entreprise.",
            "conditions": "Confirmer le périmètre, les outils et les périodes de clôture.",
            "plan": "Conduire deux entretiens métier puis comparer les offres du territoire.",
            "suite": "Reprendre les résultats des entretiens lors du prochain échange."}


def test_go24_full_conclusion_relecture_closure_and_six_month_followup(Session, engine):
    coach, beneficiary, case_id = _contexts_and_case(Session, str(engine.url))
    version = save_results(coach, case_id, _results(), publish=True, database_url=str(engine.url))
    assert version == 1
    assert read_conclusion(beneficiary, case_id, database_url=str(engine.url))["results"]["state"] == "PUBLIE_POUR_RELECTURE"
    results = read_conclusion(beneficiary, case_id, database_url=str(engine.url))["results"]
    respond_to_conclusion(beneficiary, case_id, artifact_version_id=results["id"], object_type="RESULTS",
        response="CONFIRME", database_url=str(engine.url))

    save_synthesis(coach, case_id, _synthesis(), publish=True, database_url=str(engine.url))
    synthesis = read_conclusion(beneficiary, case_id, database_url=str(engine.url))["synthesis"]
    respond_to_conclusion(beneficiary, case_id, artifact_version_id=synthesis["id"], object_type="SYNTHESIS",
        response="CONFIRME", database_url=str(engine.url))
    finalize_synthesis(coach, case_id, artifact_version_id=synthesis["id"], database_url=str(engine.url))
    save_followup_plan(coach, case_id, planned_for=_six_month_date(), database_url=str(engine.url))
    close_bilan(coach, case_id, retention_action="CONSERVATION_SELON_REGLES", database_url=str(engine.url))
    closed = read_conclusion(beneficiary, case_id, database_url=str(engine.url))
    assert closed["closed"] is True
    assert closed["synthesis"]["state"] == "FINALISEE"
    assert closed["followup"]["status"] == "PLANIFIE"
    with Session() as session:
        plan = session.query(FollowUpPlan).filter_by(case_id=case_id).one()
        plan.planned_for = date.today().isoformat()  # Simulate the six-month point arriving.
        session.commit()
    submit_followup_response(beneficiary, case_id,
        content="Le bénéficiaire a réalisé les entretiens et souhaite poursuivre ses candidatures.",
        database_url=str(engine.url))
    assert read_conclusion(beneficiary, case_id, database_url=str(engine.url))["followup"]["status"] == "REALISE"


def test_go24_blocks_synthesis_before_result_confirmation(Session, engine):
    coach, _beneficiary, case_id = _contexts_and_case(Session, str(engine.url))
    save_results(coach, case_id, _results(), publish=True, database_url=str(engine.url))
    with pytest.raises(ValueError, match="confirmée par le bénéficiaire"):
        save_synthesis(coach, case_id, _synthesis(), publish=True, database_url=str(engine.url))


def test_go24_requires_official_source_for_mandatory_diploma(Session, engine):
    coach, _beneficiary, case_id = _contexts_and_case(Session, str(engine.url))
    payload = _results()
    payload["diploma_status"] = "Diplôme requis pour exercer."
    payload["diploma_source"] = ""
    with pytest.raises(ValueError, match="source officielle"):
        save_results(coach, case_id, payload, publish=True, database_url=str(engine.url))
