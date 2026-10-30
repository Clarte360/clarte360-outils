from __future__ import annotations

import pytest

from clarte360_cp.application.go23 import CRITERIA, publish_project_decision, record_project_decision, save_comparison
from clarte360_cp.application.go24 import read_action_plan, respond_to_action_plan, save_action_plan
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import JobTarget
from tests.helpers import context


def _decision_case(Session, database_url):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_PUBLISH"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        target = JobTarget(case_id=case.case_id, rome_code="M1203", rome_label="Comptable", status="ACTIVE")
        session.add(target); session.commit()
        case_id, target_id = case.case_id, target.job_target_id
    save_comparison(coach, case_id, [{"job_target_id": target_id, "criterion": criterion,
        "content": "À vérifier avec une source datée avant de tirer une conclusion."} for criterion in CRITERIA],
        publish=True, database_url=database_url)
    decision_id = record_project_decision(coach, case_id, job_target_id=target_id, decision_type="PRIORITAIRE",
        wording="Le bénéficiaire retient cette piste en lien avec ses acquis et ses conditions recherchées.",
        database_url=database_url)
    publish_project_decision(coach, case_id, decision_id=decision_id, database_url=database_url)
    return coach, case_id


def test_go24_action_plan_is_published_explicitly_and_beneficiary_can_respond(Session, engine):
    coach, case_id = _decision_case(Session, str(engine.url))
    rows = [{"action": "Réaliser deux entretiens métier", "due": "Avant fin novembre",
             "means": "Préparer une trame avec l'accompagnateur", "expected": "Vérifier les contraintes d'exercice"}]
    save_action_plan(coach, case_id, rows, database_url=str(engine.url))
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_VALIDATE"], actor="BEN-1")
    assert read_action_plan(beneficiary, case_id, database_url=str(engine.url))["items"] == ()
    version = save_action_plan(coach, case_id, rows, publish=True, database_url=str(engine.url))
    assert version == 2
    plan = read_action_plan(beneficiary, case_id, database_url=str(engine.url))
    assert plan["state"] == "PUBLIEE"
    assert plan["items"][0]["means"] == "Préparer une trame avec l'accompagnateur"
    respond_to_action_plan(beneficiary, case_id, plan_id=plan["plan_id"], response="CONFIRME",
                           database_url=str(engine.url))
    assert read_action_plan(beneficiary, case_id, database_url=str(engine.url))["beneficiary_response"] == "EXPLICITE"
    with pytest.raises(ValueError, match="déjà été donnée"):
        respond_to_action_plan(beneficiary, case_id, plan_id=plan["plan_id"], response="CONFIRME",
                               database_url=str(engine.url))


def test_go24_action_plan_requires_prior_project_decision(Session, engine):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        case_id = case.case_id
    with pytest.raises(ValueError, match="projet prioritaire"):
        save_action_plan(coach, case_id, [{"action": "Rechercher une immersion"}], database_url=str(engine.url))


def test_go24_adjustment_requires_a_comment(Session, engine):
    coach, case_id = _decision_case(Session, str(engine.url))
    save_action_plan(coach, case_id, [{"action": "Réaliser deux entretiens métier"}], publish=True,
                     database_url=str(engine.url))
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_VALIDATE"], actor="BEN-1")
    plan = read_action_plan(beneficiary, case_id, database_url=str(engine.url))
    with pytest.raises(ValueError, match="Précisez le point"):
        respond_to_action_plan(beneficiary, case_id, plan_id=plan["plan_id"], response="AJUSTEMENT_DEMANDE",
                               database_url=str(engine.url))
