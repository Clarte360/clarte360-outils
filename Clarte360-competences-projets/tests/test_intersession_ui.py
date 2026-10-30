from __future__ import annotations

import json

from streamlit.testing.v1 import AppTest

from clarte360_cp.application.intersession import read_intersession_tasks
from clarte360_cp.application.rome_matching import save_rome_matching_review
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import ExternalSnapshot, JobTarget
from tests.helpers import context


def _coach_page(ctx, case_id):
    from clarte360_cp.ui.rome_workshop import render_rome_investigations
    render_rome_investigations(ctx, case_id)


def _beneficiary_page(ctx, case_id):
    import streamlit as st
    from clarte360_cp.ui.beneficiaire import render_intersession
    render_intersession(ctx, case_id)


def _label(elements, label):
    return next(element for element in elements if element.label == label)


def test_investigation_can_be_assigned_completed_and_returned_for_debrief(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context()
    beneficiary = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT"])
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        case_id = case.case_id
        target = JobTarget(case_id=case_id, rome_code="M1203", rome_label="Comptable", status="ACTIVE")
        session.add(target)
        session.commit()
        job_target_id = target.job_target_id

    coach_app = AppTest.from_function(_coach_page, args=(coach, case_id), default_timeout=10).run()
    assert not coach_app.exception and not coach_app.error
    _label(coach_app.selectbox, "Métier ROME concerné par cette investigation").set_value("M1203 — Comptable")
    _label(coach_app.selectbox, "Nature de la vérification").set_value("OFFRES_EMPLOI")
    _label(coach_app.text_area, "Question ou objectif confié au bénéficiaire").set_value(
        "Comparer deux offres de comptable sur le territoire visé et relever les compétences demandées."
    )
    _label(coach_app.button, "Transmettre cette action au bénéficiaire").click().run()
    assert not coach_app.exception and not coach_app.error
    task = read_intersession_tasks(coach, case_id, database_url=str(engine.url))[0]
    assert task["task_type"] == "OFFRES_EMPLOI"
    assert task["state"] == "PUBLIEE"
    assert task["job_target_id"] == job_target_id
    assert task["job_target_label"] == "Comptable"

    beneficiary_app = AppTest.from_function(_beneficiary_page, args=(beneficiary, case_id), default_timeout=10).run()
    assert not beneficiary_app.exception and not beneficiary_app.error
    assert any("Comptable" in item.value for item in beneficiary_app.caption)
    assert any("que les API soient disponibles ou non" in item.value for item in beneficiary_app.caption)
    assert any("Offres d'emploi — France Travail" == item.label for item in beneficiary_app.link_button)
    _label(beneficiary_app.text_input, "1. Source consultée").set_value("France Travail")
    _label(beneficiary_app.text_input, "2. Date de consultation").set_value("2026-10-23")
    _label(beneficiary_app.text_area, "3. Ce que j’ai appris").set_value(
        "Les deux offres demandent le suivi des comptes clients et la maîtrise d'Excel."
    )
    _label(beneficiary_app.text_area, "4. Ce que cela confirme, modifie ou laisse à vérifier dans mon projet").set_value(
        "Cela confirme mon intérêt ; le niveau Excel reste à vérifier."
    )
    _label(beneficiary_app.button, "Envoyer mon retour à l’accompagnateur").click().run()
    assert not beneficiary_app.exception and not beneficiary_app.error
    returned = read_intersession_tasks(coach, case_id, database_url=str(engine.url))[0]
    assert returned["state"] == "SOUMISE"
    assert returned["response"]["source"] == "France Travail"
    assert returned["response"]["project_impact"].startswith("Cela confirme")


def test_accompanist_can_prepare_targeted_mission_from_unresolved_rome_review(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context()
    payload = {"code_rome": "M1203", "intitule": "Comptable", "version": "ROME-4-test",
        "competences": {"savoirs": {"categories": [{"libelle": "Expertise", "items": [
            {"libelle": "Clôture comptable", "code_ogr": "117781"}]}]}}}
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        snapshot = ExternalSnapshot(case_id=case.case_id, provider="FRANCE_TRAVAIL", resource_type="ROME_FICHE_METIER",
            external_key="M1203", payload_json=json.dumps(payload), sha256="c" * 64,
            effective_date="2026-10-24")
        session.add(snapshot); session.flush()
        target = JobTarget(case_id=case.case_id, rome_code="M1203", rome_label="Comptable",
            snapshot_id=snapshot.snapshot_id, status="ACTIVE", selected_order=1)
        session.add(target); session.commit()
        case_id, target_id = case.case_id, target.job_target_id
    save_rome_matching_review(coach, case_id, target_id, [{
        "rome_item_key": "SAVOIR:117781", "status": "NON_DOCUMENTE", "experience_ids": [],
        "rationale": "Aucun exemple de ce savoir n'est encore présent dans les informations partagées.",
    }], database_url=str(engine.url))

    app = AppTest.from_function(_coach_page, args=(coach, case_id), default_timeout=10).run()
    assert not app.exception and not app.error
    point = "M1203 — Comptable · SAVOIR · Clôture comptable"
    _label(app.selectbox, "Point de l’analyse à approfondir").set_value(point).run()
    _label(app.button, "Préparer une mission à partir de ce point").click().run()
    assert not app.exception and not app.error
    goal = _label(app.text_area, "Question ou objectif confié au bénéficiaire").value
    assert "Clôture comptable" in goal
    assert _label(app.selectbox, "Métier ROME concerné par cette investigation").value == "M1203 — Comptable"
