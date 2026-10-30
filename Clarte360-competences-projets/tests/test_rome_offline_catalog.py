from __future__ import annotations

from streamlit.testing.v1 import AppTest

from clarte360_cp.application.rome_catalog import (
    _local_catalog, decide_rome_target, prepare_local_rome_target,
    read_local_rome_metadata, read_rome_targets, search_local_rome,
)
from clarte360_cp.application.rome_matching import read_rome_matching_workspace
from clarte360_cp.repositories.cases import CaseRepository
from tests.helpers import context


def _render_selection(ctx, case_id):
    from clarte360_cp.ui.rome_workshop import render_rome_target_selection
    render_rome_target_selection(ctx, case_id)


def test_packaged_rome_reference_has_official_version_and_stable_skill_codes():
    catalog = _local_catalog()
    assert catalog["version"] == "ROME 4.0 version 61 (26M06)"
    assert catalog["publication_date"] == "2026-06-15"
    assert catalog["entry_count"] == len(catalog["items"]) == 1911
    assert len({row["code"] for row in catalog["items"]}) == 1911
    assert all(row.get("intitule") and row.get("definition") and row.get("competences")
               for row in catalog["items"])
    assert read_local_rome_metadata() == {
        "version": "ROME 4.0 version 61 (26M06)",
        "publication_date": "2026-06-15",
        "entry_count": 1911,
        "source_file": catalog["source_file"],
    }
    matches = search_local_rome("comptable")
    assert any(row == {"code": "M1203", "label": "Comptable"} for row in matches)


def test_local_rome_fiche_supports_selection_and_in_session_matching_without_api(Session, engine):
    ctx = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(ctx)
        case_id = case.case_id

    proposal = prepare_local_rome_target(ctx, case_id, "m1203", database_url=str(engine.url))
    assert proposal["status"] == "PROPOSITION"
    assert proposal["source_provider"] == "FRANCE_TRAVAIL_OPENDATA"
    targets = read_rome_targets(ctx, case_id, database_url=str(engine.url))
    assert targets[0]["source_date"] == "2026-06-15"
    assert targets[0]["source_version"] == "ROME 4.0 version 61 (26M06)"
    assert targets[0]["access_description"].startswith("Cet emploi est accessible")

    assert decide_rome_target(ctx, case_id, proposal["job_target_id"], accept=True,
        database_url=str(engine.url)) == "ACTIVE"

    workspace = read_rome_matching_workspace(ctx, case_id, database_url=str(engine.url))
    target = workspace.targets[0]
    assert len(target.items) > 0
    assert any(item.label == "Comptabilité générale" for item in target.items)


def test_accompanist_can_search_and_propose_local_rome_without_api(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    ctx = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(ctx)
        case_id = case.case_id

    app = AppTest.from_function(_render_selection, args=(ctx, case_id), default_timeout=10).run()
    assert not app.exception and not app.error
    assert not app.warning
    assert any("Le bénéficiaire n’a pas de recherche ROME externe à faire" in item.value for item in app.markdown)
    next(widget for widget in app.text_input if widget.label == "Rechercher un code, un métier ou une appellation").set_value("M1203")
    next(widget for widget in app.button if widget.label == "Rechercher dans le ROME").click().run()
    assert not app.exception and not app.error
    results = next(widget for widget in app.selectbox if widget.label == "Métiers ROME correspondants")
    assert any("M1203 — Comptable" in option for option in results.options)
    next(widget for widget in app.button if widget.label == "Utiliser la fiche locale datée").click().run()
    assert not app.exception and not app.error
    targets = read_rome_targets(ctx, case_id, database_url=str(engine.url))
    assert targets[0]["code"] == "M1203"
    assert targets[0]["status"] == "PROPOSITION"


def test_accompanist_can_load_selected_search_result_from_rome_fiche_api(Session, engine, monkeypatch):
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    ctx = context()
    with Session() as session:
        case = CaseRepository(session).open_or_create(ctx)
        case_id = case.case_id
    calls = []

    def fake_api(_ctx, _case_id, code, *, force_refresh=False):
        calls.append((code, force_refresh))
        return {"code": code, "label": "Comptable", "status": "PROPOSITION"}

    monkeypatch.setattr("clarte360_cp.ui.rome_workshop.prepare_rome_target", fake_api)
    app = AppTest.from_function(_render_selection, args=(ctx, case_id), default_timeout=10).run()
    next(widget for widget in app.text_input if widget.label == "Rechercher un code, un métier ou une appellation").set_value("M1203")
    next(widget for widget in app.button if widget.label == "Rechercher dans le ROME").click().run()
    assert not app.exception and not app.error
    next(widget for widget in app.button if widget.label == "Charger la fiche à jour depuis l’API").click().run()
    assert not app.exception and not app.error
    assert calls == [("M1203", True)]

