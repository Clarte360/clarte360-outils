from __future__ import annotations

import json
import pytest

from streamlit.testing.v1 import AppTest

from clarte360_cp.application.rome_matching import read_rome_matching_workspace
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import CareerItem, ExternalSnapshot, JobTarget
from tests.helpers import context


def _render(ctx, case_id):
    from clarte360_cp.ui.rome_workshop import render_rome_matching
    render_rome_matching(ctx, case_id)


def _render_career(ctx, case_id):
    from clarte360_cp.ui.rome_workshop import render_career_enrichment
    render_career_enrichment(ctx, case_id)


def _render_target_selection(ctx, case_id):
    from clarte360_cp.ui.rome_workshop import render_rome_target_selection
    render_rome_target_selection(ctx, case_id)


def _label(elements, label):
    return next(element for element in elements if element.label == label)


def test_accompanist_can_load_direct_rome_code_from_api_when_missing_from_local_index(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        session.commit()
        case_id = case.case_id

    calls = []
    def fake_prepare(_ctx, _case_id, code, *, force_refresh=False):
        calls.append((code, force_refresh))
        return {"code": code, "label": "Métier test API"}

    monkeypatch.setattr("clarte360_cp.ui.rome_workshop.prepare_rome_target", fake_prepare)
    app = AppTest.from_function(_render_target_selection, args=(coach, case_id), default_timeout=10).run()
    _label(app.text_input, "Code ROME direct (interrogation France Travail)").set_value("Z9999").run()
    _label(app.button, "Charger ce code depuis l’API France Travail").click().run()

    assert not app.exception and not app.error
    assert calls == [("Z9999", True)]


def test_accompanist_searches_rome_api_before_showing_in_app_results(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        session.commit()
        case_id = case.case_id

    calls = []
    monkeypatch.setattr("clarte360_cp.ui.rome_workshop.search_rome_metiers",
        lambda query, *, limit: calls.append((query, limit)) or ({"code": "Z9999", "label": "Métier API"},))
    monkeypatch.setattr("clarte360_cp.ui.rome_workshop.search_local_rome",
        lambda *_a, **_k: pytest.fail("the dated local fallback must not override API search results"))
    app = AppTest.from_function(_render_target_selection, args=(coach, case_id), default_timeout=10).run()
    _label(app.text_input, "Rechercher un code, un métier ou une appellation").set_value("métier API")
    _label(app.button, "Rechercher dans le ROME").click().run()

    assert not app.exception and not app.error
    assert calls == [("métier API", 60)]
    assert _label(app.selectbox, "Métiers ROME correspondants").options == ["Z9999 — Métier API"]
    assert any("API France Travail · ROME Métiers" in item.value for item in app.caption)


def test_accompanist_falls_back_to_dated_local_rome_index_if_api_search_fails(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        session.commit()
        case_id = case.case_id

    from clarte360_cp.application.rome_catalog import RomeCatalogError
    monkeypatch.setattr("clarte360_cp.ui.rome_workshop.search_rome_metiers",
        lambda *_a, **_k: (_ for _ in ()).throw(RomeCatalogError("France Travail a répondu avec le statut HTTP 403.")))
    monkeypatch.setattr("clarte360_cp.ui.rome_workshop.search_local_rome",
        lambda query, *, limit: ({"code": "M1203", "label": "Comptable"},))
    app = AppTest.from_function(_render_target_selection, args=(coach, case_id), default_timeout=10).run()
    _label(app.text_input, "Rechercher un code, un métier ou une appellation").set_value("comptable")
    _label(app.button, "Rechercher dans le ROME").click().run()

    assert not app.exception and not app.error
    assert _label(app.selectbox, "Métiers ROME correspondants").options == ["M1203 — Comptable"]
    assert any("Référentiel local daté" in item.value for item in app.caption)
    assert any("HTTP 403" in item.value for item in app.caption)


def test_accompanist_can_select_and_link_a_rome_item_in_shared_session(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context()
    payload = {
        "code_rome": "M1203", "intitule": "Comptable", "version": "ROME-4.0-test",
        "competences": {"savoirs": {"categories": [{"libelle": "Expertise", "items": [
            {"libelle": "Comptabilité client", "code_ogr": "117781"},
        ]}] }},
    }
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        snapshot = ExternalSnapshot(
            case_id=case.case_id, provider="FRANCE_TRAVAIL", resource_type="ROME_FICHE_METIER",
            external_key="M1203", payload_json=json.dumps(payload), sha256="a" * 64,
            effective_date="2026-10-23",
        )
        session.add(snapshot)
        session.flush()
        target = JobTarget(
            case_id=case.case_id, rome_code="M1203", rome_label="Comptable",
            snapshot_id=snapshot.snapshot_id, status="ACTIVE", selected_order=1,
        )
        experience = CareerItem(
            case_id=case.case_id, item_type="ETUDE", title="Études de comptabilité sans diplôme",
            details_json=json.dumps({"activities": "Étude des écritures comptables et exercices sur les comptes clients."}),
            status="ACTIVE",
        )
        session.add_all([target, experience])
        session.commit()
        case_id, item_id = case.case_id, experience.career_item_id

    app = AppTest.from_function(_render, args=(coach, case_id), default_timeout=10).run()
    assert not app.exception
    assert not app.error, [getattr(x, "value", repr(x)) for x in app.error]
    assert any("Aide de séance" in item.label for item in app.expander)
    level = _label(app.selectbox, "Niveau d’exercice discuté pour cette expérience")
    assert level.options == [
        "À préciser avec le bénéficiaire",
        "1 — Pratique encadrée / contribution",
        "2 — Maîtrise autonome",
        "3 — Pilotage, expertise ou transmission",
    ]

    checkbox = _label(app.checkbox, "Comptabilité client")
    checkbox.check().run()
    assert not app.exception
    assert "Sélection en cours : 1 attendu(s)" in "\n".join(x.value for x in app.markdown)

    evidence_selector = _label(app.multiselect, "Élément(s) du parcours qui étayent ce savoir")
    assert evidence_selector.options == ["Études — Études de comptabilité sans diplôme · " + item_id[:8]]
    evidence_selector.set_value(evidence_selector.options)
    _label(app.selectbox, "Statut après échange").set_value("ACQUIS_ETAYE")
    _label(app.selectbox, "Niveau d’exercice de ce savoir, discuté en séance").set_value("2 — Maîtrise autonome")
    _label(app.button, "Enregistrer le rapprochement de la sélection").click().run()

    assert not app.exception and not app.error
    workspace = read_rome_matching_workspace(coach, case_id, database_url=str(engine.url))
    review = workspace.current_reviews[0][2]
    assert review["items"][0]["status"] == "ACQUIS_ETAYE"
    assert review["items"][0]["exercise_level"] == 2
    assert review["items"][0]["experiences"][0]["title"] == "Études de comptabilité sans diplôme"

    reopened = AppTest.from_function(_render, args=(coach, case_id), default_timeout=10).run()
    assert not reopened.exception and not reopened.error
    assert _label(reopened.checkbox, "Comptabilité client").value is True
    assert _label(reopened.selectbox, "Statut après échange").value == "ACQUIS_ETAYE"
    assert _label(reopened.multiselect, "Élément(s) du parcours qui étayent ce savoir").value == [
        "Études — Études de comptabilité sans diplôme · " + item_id[:8]
    ]
    assert _label(reopened.selectbox, "Niveau d’exercice de ce savoir, discuté en séance").value == "2 — Maîtrise autonome"
    _label(reopened.selectbox, "Niveau d’exercice de ce savoir, discuté en séance").set_value(
        "3 — Pilotage, expertise ou transmission")
    _label(reopened.button, "Enregistrer le rapprochement de la sélection").click().run()
    assert not reopened.exception and not reopened.error
    revised = read_rome_matching_workspace(coach, case_id, database_url=str(engine.url))
    assert revised.current_reviews[0][2]["items"][0]["exercise_level"] == 3


def test_career_enrichment_screen_discloses_shared_document_boundary(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        session.add(CareerItem(case_id=case.case_id, item_type="ETUDE", title="Comptabilité étudiée",
            details_json=json.dumps({"activities": "Écritures comptables"}), status="ACTIVE"))
        session.commit()
        case_id = case.case_id
    app = AppTest.from_function(_render_career, args=(coach, case_id), default_timeout=10).run()
    assert not app.exception and not app.error
    assert any("reste dans l’espace commun GDA" in x.value for x in app.info)
    assert any("Comptabilité étudiée" in x.label for x in app.expander)


def test_career_enrichment_can_add_a_session_card_before_rome_selection(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    coach = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(coach)
        session.commit()
        case_id = case.case_id
    app = AppTest.from_function(_render_career, args=(coach, case_id), default_timeout=10).run()
    title = _label(app.text_input, "Intitulé de l’expérience, des études ou de la formation")
    title.set_value("Études de comptabilité sans diplôme")
    _label(app.text_area, "Activités, contenus étudiés ou missions").set_value("Étude du plan comptable et exercices de rapprochement.")
    _label(app.selectbox, "Nature de l’élément").set_value("ETUDE")
    _label(app.button, "Ajouter au parcours").click().run()
    assert not app.exception and not app.error
    assert any("Études de comptabilité sans diplôme" in x.label for x in app.expander)
