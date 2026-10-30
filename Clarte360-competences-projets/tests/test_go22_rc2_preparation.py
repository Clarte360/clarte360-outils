"""GO22 RC2 : tests du parcours Q-V1 / R-V1 / R-V2, sans réseau IA."""
from __future__ import annotations

import copy

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DatabaseError

from clarte360_cp.application.preparation import (
    cav3_context, confirm_joint_review, create_questionnaire, lock_questionnaire,
    open_beneficiary_access, read_preparation, response_history,
    save_beneficiary_answers, save_joint_review, save_questionnaire,
    submit_beneficiary_answers,
)
from clarte360_cp.application.orientation import OrientationAccessDenied, OrientationConflict
from clarte360_cp.domain.preparation import (
    empty_answers, generate_questionnaire, valid_answers,
)
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import (
    AuditEvent, PreparationQuestionnaire, PreparationResponse, SchemaMigration, Validation,
)
from tests.helpers import context

ACC = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_VALIDATE", "CP_PUBLISH"]
BEN = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT", "CP_BENEFICIARY_VALIDATE"]


@pytest.fixture
def setup_rc2(engine, Session):
    coach = context(scopes=ACC, actor="ACCOMPAGNE-1")
    beneficiary = context(role="BENEFICIAIRE", scopes=BEN, actor="PERSONNE-1")
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        cid = case.case_id
    sources = {
        "APS_OBJECTIF": {"source_ref": "APS-REF-v2", "authorized": True, "idea_list": ["muséographe", "préparatrice en pharmacie"]},
        "BOUSSOLE_VALEURS": {"source_ref": "BOUSSOLE-v1", "authorized": True, "items": ["Respect", "Créativité", "Autonomie", "Intégrité"]},
        "MOTEURS_PRO": {"source_ref": "MOTEURS-v1", "authorized": True},
        "PREFERENCES_PRO": {"source_ref": "PREF-v1", "authorized": True,
                              "items_go": ["Autonomie avec cadre clair", "Activité variée"],
                              "items_no_go": ["Micro-management permanent", "Répétitivité excessive"]},
        "IPIP_REPORT": {"source_ref": "NEO-v1", "authorized": True, "items": ["Temps de réflexion", "Relations constructives"]},
        "PIP_REPORT": {"source_ref": "PIP-v1", "authorized": True, "items": ["Concevoir un espace", "Développer une activité", "Rencontrer des clients"]},
        "ENTREPRISE_PERSPECTIVE": {"source_ref": "EMP-SECRET", "authorized": False, "wording": "Mobilité interne"},
    }
    return str(engine.url), cid, coach, beneficiary, sources


def prepare(setup_rc2):
    url, cid, coach, ben, sources = setup_rc2
    generated = create_questionnaire(coach, cid, sources, context="AUTOFINANCE", database_url=url)
    locked = lock_questionnaire(coach, cid, expected_row_version=generated.row_version, database_url=url)
    opened = open_beneficiary_access(coach, cid, expected_row_version=locked.row_version, database_url=url)
    return url, cid, coach, ben, opened


def filled(view):
    d = empty_answers(view.questionnaire)
    d["ideas"] = [{"wording": "préparatrice en pharmacie",
                   "meaning": ["Rejoindre une organisation précise", "Explorer une opportunité"],
                   "status": ["Entreprise familiale"], "attraction": ["Responsabilités et autonomie"],
                   "access": ["Reste à vérifier"], "note": "Projet familial à préciser"}]
    sections = {x["code"]: x for x in view.questionnaire["sections"]}
    for k in sections:
        if sections[k]["required"]:
            d["selections"][k] = sections[k]["choices"][:1]
    d["selections"]["VALEURS"] = ["Créativité", "Autonomie"]
    return d


def test_questionnaire_is_neutral_and_employer_is_separate(setup_rc2):
    *_, sources = setup_rc2
    q = generate_questionnaire(sources, context="AUTOFINANCE")
    assert q["aps_ideas"] == ["muséographe", "préparatrice en pharmacie"]
    assert q["enterprise_wording"] == ""
    assert all(x["code"] != "ENTREPRISE_PERSPECTIVE" for x in q["source_refs"])
    assert "CV_SOURCE" not in str(q)
    assert "IA" not in q["schema"]


def test_values_not_preselected_or_generated_from_scores(setup_rc2):
    *_, sources = setup_rc2
    sources["BOUSSOLE_VALEURS"]["energy_selections"] = ["Créativité", "Autonomie"]
    sources["BOUSSOLE_VALEURS"]["scores"] = [9.9, 8.1]
    q = generate_questionnaire(sources)
    d = empty_answers(q)
    assert not d["selections"]["VALEURS"]
    assert not any("energy_selections" in str(x) for x in q.values())
    d["selections"]["VALEURS"] = ["Autonomie", "Créativité", "Respect", "Intégrité"]
    with pytest.raises(ValueError, match="valeurs indispensables"):
        valid_answers(d, q)


def test_beneficiary_cannot_see_before_lock_and_invite(setup_rc2):
    url, cid, coach, ben, sources = setup_rc2
    draft = create_questionnaire(coach, cid, sources, database_url=url)
    assert draft.stage == "QUESTIONNAIRE_BROUILLON"
    assert read_preparation(ben, cid, database_url=url).questionnaire is None
    locked = lock_questionnaire(coach, cid, expected_row_version=draft.row_version, database_url=url)
    assert read_preparation(ben, cid, database_url=url).questionnaire is None
    accessed = open_beneficiary_access(coach, cid, expected_row_version=locked.row_version, database_url=url)
    assert read_preparation(ben, cid, database_url=url).questionnaire_locked
    with pytest.raises(ValueError, match="verrouillé"):
        save_questionnaire(coach, cid, locked.questionnaire, expected_row_version=accessed.row_version, database_url=url)


def test_no_idea_is_valid_without_any_tools(setup_rc2):
    url, cid, coach, ben, sources = setup_rc2
    d = create_questionnaire(coach, cid, {}, database_url=url)
    l = lock_questionnaire(coach, cid, expected_row_version=d.row_version, database_url=url)
    open_beneficiary_access(coach, cid, expected_row_version=l.row_version, database_url=url)
    v = read_preparation(ben, cid, database_url=url)
    a = empty_answers(v.questionnaire)
    a["no_idea_yet"] = True
    x = save_beneficiary_answers(ben, cid, a, expected_row_version=v.row_version, database_url=url)
    y = submit_beneficiary_answers(ben, cid, expected_row_version=x.row_version, database_url=url)
    assert y.active_answers["no_idea_yet"]
    assert cav3_context(coach, cid, database_url=url)["status"] == "PREPARATOIRE_NON_VALIDE"


def test_beneficiary_draft_and_final_are_separate_immutable(setup_rc2, Session):
    url, cid, coach, ben, opened = prepare(setup_rc2)
    a = filled(opened)
    draft = save_beneficiary_answers(ben, cid, a, expected_row_version=opened.row_version, database_url=url)
    a["observations"]["VALEURS"] = "Besoin de pouvoir créer"
    newer = save_beneficiary_answers(ben, cid, a, expected_row_version=draft.row_version, database_url=url)
    final = submit_beneficiary_answers(ben, cid, expected_row_version=newer.row_version, database_url=url)
    assert final.active_answers["observations"]["VALEURS"] == "Besoin de pouvoir créer"
    with pytest.raises(ValueError, match="définitivement"):
        save_beneficiary_answers(ben, cid, a, expected_row_version=final.row_version, database_url=url)
    with Session() as s:
        r = s.scalar(select(PreparationResponse).where(PreparationResponse.state == "BENEFICIAIRE_VALIDE"))
        r.content_json = "{}"
        with pytest.raises(DatabaseError):
            s.commit()


def test_joint_review_preserves_r1_and_promotes_only_after_two_agreements(setup_rc2, Session):
    url, cid, coach, ben, opened = prepare(setup_rc2)
    a = filled(opened)
    draft = save_beneficiary_answers(ben, cid, a, expected_row_version=opened.row_version, database_url=url)
    first = submit_beneficiary_answers(ben, cid, expected_row_version=draft.row_version, database_url=url)
    r1 = first.active_response_version
    revised = copy.deepcopy(a)
    revised["selections"]["VALEURS"] = ["Respect", "Créativité"]
    pending = save_joint_review(coach, cid, revised, expected_row_version=first.row_version, database_url=url)
    assert pending.active_response_version == r1
    assert cav3_context(coach, cid, database_url=url)["reponses"]["selections"]["VALEURS"] == ["Créativité", "Autonomie"]
    with pytest.raises(ValueError, match="Confirmation expresse"):
        confirm_joint_review(coach, cid, beneficiary_confirmed=False, method="PARTAGE_ECRAN_ORAL", expected_row_version=pending.row_version, database_url=url)
    joint = confirm_joint_review(coach, cid, beneficiary_confirmed=True, method="PARTAGE_ECRAN_ORAL", expected_row_version=pending.row_version, database_url=url)
    assert joint.active_response_version > r1
    assert joint.active_answers["selections"]["VALEURS"] == ["Respect", "Créativité"]
    assert joint.reviewed_in_session
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(PreparationResponse).where(PreparationResponse.state == "BENEFICIAIRE_VALIDE")) == 1
        assert s.scalar(select(func.count()).select_from(PreparationResponse).where(PreparationResponse.state == "REVUE_CONJOINTE")) == 1
        assert s.scalar(select(func.count()).select_from(Validation).where(Validation.event_key.like("CAV:JOINT_%"))) == 2
        assert s.get(SchemaMigration, "3") is not None


def test_no_changes_means_no_fake_r2(setup_rc2):
    url, cid, coach, ben, opened = prepare(setup_rc2)
    v = save_beneficiary_answers(ben, cid, filled(opened), expected_row_version=opened.row_version, database_url=url)
    first = submit_beneficiary_answers(ben, cid, expected_row_version=v.row_version, database_url=url)
    accepted = confirm_joint_review(coach, cid, beneficiary_confirmed=True, method="EN_SEANCE_PRESENTIEL", expected_row_version=first.row_version, database_url=url)
    assert accepted.active_response_version == first.active_response_version
    assert accepted.reviewed_in_session
    with pytest.raises(ValueError, match="déjà été revue"):
        confirm_joint_review(coach, cid, beneficiary_confirmed=True, method="EN_SEANCE_PRESENTIEL", expected_row_version=accepted.row_version, database_url=url)


def test_stale_edit_and_access_is_denied(setup_rc2):
    url, cid, coach, ben, opened = prepare(setup_rc2)
    with pytest.raises(OrientationConflict):
        save_beneficiary_answers(ben, cid, filled(opened), expected_row_version=0, database_url=url)
    with pytest.raises(OrientationAccessDenied):
        save_joint_review(ben, cid, filled(opened), expected_row_version=opened.row_version, database_url=url)
    with pytest.raises(OrientationAccessDenied):
        cav3_context(ben, cid, database_url=url)
    wrong = context(scopes=ACC, beneficiary="OTHER-PERSON", actor="OTHER")
    with pytest.raises(OrientationAccessDenied):
        read_preparation(wrong, cid, database_url=url)


def test_choices_must_belong_to_locked_questionnaire(setup_rc2):
    url, cid, coach, ben, opened = prepare(setup_rc2)
    a = filled(opened)
    a["selections"]["PIP_ATTRACTION"] = ["Un métier inventé par l'IA"]
    with pytest.raises(ValueError, match="choix"):
        save_beneficiary_answers(ben, cid, a, expected_row_version=opened.row_version, database_url=url)


def test_missing_required_section_needs_explicit_none_reason(setup_rc2):
    url, cid, coach, ben, opened = prepare(setup_rc2)
    a = filled(opened)
    a["selections"]["MOTEURS_ESSENTIELS"] = []
    v = save_beneficiary_answers(ben, cid, a, expected_row_version=opened.row_version, database_url=url)
    with pytest.raises(ValueError, match="moteurs essentiels"):
        submit_beneficiary_answers(ben, cid, expected_row_version=v.row_version, database_url=url)
    a["none_reasons"]["MOTEURS_ESSENTIELS"] = "AUCUN_CRITERE_IDENTIFIE"
    v2 = save_beneficiary_answers(ben, cid, a, expected_row_version=v.row_version, database_url=url)
    assert submit_beneficiary_answers(ben, cid, expected_row_version=v2.row_version, database_url=url).active_answers


def test_no_private_content_leaked_in_audit(setup_rc2, Session):
    url, cid, coach, ben, opened = prepare(setup_rc2)
    a = filled(opened)
    a["ideas"][0]["note"] = "Confidentiel — famille et situation personnelle"
    v = save_beneficiary_answers(ben, cid, a, expected_row_version=opened.row_version, database_url=url)
    submit_beneficiary_answers(ben, cid, expected_row_version=v.row_version, database_url=url)
    with Session() as s:
        events = s.scalars(select(AuditEvent).where(AuditEvent.case_id == cid)).all()
        assert all("Confidentiel" not in (x.metadata_json_minimized or "") for x in events)


def test_business_context_cannot_be_guessed_from_family_project(setup_rc2):
    *_, sources = setup_rc2
    s = copy.deepcopy(sources)
    s["ENTREPRISE_PERSPECTIVE"] = {"source_ref": "EMP", "wording": "Commercial", "authorized": True}
    with pytest.raises(ValueError, match="tripartite"):
        generate_questionnaire(s, context="AUTOFINANCE")


def test_existing_aps_ideas_are_never_implicitly_confirmed(setup_rc2):
    *_, sources = setup_rc2
    q = generate_questionnaire(sources, context="AUTOFINANCE")
    d = empty_answers(q)
    assert q["aps_ideas"] == ["muséographe", "préparatrice en pharmacie"]
    assert d["ideas"] == []  # seuls les choix explicitement confirmés seront actifs
    assert not d["no_idea_yet"]
    with pytest.raises(ValueError, match="Indiquez au moins une idée"):
        valid_answers(d, q, final=True)


def test_mixed_financing_and_employer_tripartite_are_not_conflated(setup_rc2):
    *_, sources = setup_rc2
    s = copy.deepcopy(sources)
    s["ENTREPRISE_PERSPECTIVE"] = {
        "source_ref": "PERSPECTIVE-EMP", "wording": "Mobilité interne évoquée",
        "authorized": True,
    }
    assert generate_questionnaire(s, context="ENTREPRISE_TRIPARTITE_MIXTE")["enterprise_wording"] == "Mobilité interne évoquée"
    with pytest.raises(ValueError, match="tripartite"):
        generate_questionnaire(s, context="FINANCEMENT_MIXTE")


def test_go_no_go_preferences_have_distinct_options(setup_rc2):
    *_, sources = setup_rc2
    q = generate_questionnaire(sources, context="AUTOFINANCE")
    sections = {s["code"]: s for s in q["sections"]}
    assert sections["PREF_GO"]["choices"] == ["Autonomie avec cadre clair", "Activité variée"]
    assert sections["PREF_NO_GO"]["choices"] == ["Micro-management permanent", "Répétitivité excessive"]
    a = empty_answers(q)
    a["selections"]["PREF_GO"] = ["Autonomie avec cadre clair"]
    a["selections"]["PREF_NO_GO"] = ["Micro-management permanent"]
    assert valid_answers(a, q)["selections"]["PREF_NO_GO"] == ["Micro-management permanent"]


def test_cannot_choose_motor_both_essential_and_optional(setup_rc2):
    *_, sources = setup_rc2
    q = generate_questionnaire(sources)
    motor = {s["code"]: s for s in q["sections"]}["MOTEURS_ESSENTIELS"]["choices"][0]
    answers = empty_answers(q)
    answers["selections"]["MOTEURS_ESSENTIELS"] = [motor]
    answers["selections"]["MOTEURS_PLUS"] = [motor]
    with pytest.raises(ValueError, match="moteur"):
        valid_answers(answers, q)


def test_questionnaire_can_be_tailored_then_locked(setup_rc2):
    url, cid, coach, ben, sources = setup_rc2
    draft = create_questionnaire(coach, cid, sources, database_url=url)
    edited = copy.deepcopy(draft.questionnaire)
    to_change = next(s for s in edited["sections"] if s["code"] == "PIP_ATTRACTION")
    to_change["question"] = "Quelles activités vous attirent aujourd'hui ?"
    to_change["choices"].append("Contribuer à un projet local")
    revised = save_questionnaire(coach, cid, edited, expected_row_version=draft.row_version, database_url=url)
    locked = lock_questionnaire(coach, cid, expected_row_version=revised.row_version, database_url=url)
    assert locked.questionnaire["sections"][-2]["code"] == "PIP_ATTRACTION"
    assert "Contribuer à un projet local" in locked.questionnaire["sections"][-2]["choices"]
    with pytest.raises(ValueError, match="verrouillé"):
        save_questionnaire(coach, cid, edited, expected_row_version=locked.row_version, database_url=url)
