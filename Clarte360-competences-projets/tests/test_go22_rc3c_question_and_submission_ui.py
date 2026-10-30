"""Recette Streamlit réelle : question par piste, publication et dernière réponse R1.

Les cas sont entièrement fictifs. Les actions UI utilisent les services et la
base SQLite du test, sans remplacer les fonctions de sauvegarde/publication.
"""
from __future__ import annotations

import copy

import pytest
from streamlit.testing.v1 import AppTest

from clarte360_cp.application.preparation import (
    create_questionnaire_v2, lock_and_publish_questionnaire, read_preparation,
    save_questionnaire, save_beneficiary_answers,
)
from clarte360_cp.domain.preparation_v2 import empty_answers_v2
from clarte360_cp.repositories.cases import CaseRepository
from tests.helpers import context
from tests.test_go22_rc3_unique_q import ACC, BEN, filled
from tools.go22_rc3_demo_seed import synthetic_sources


def _builder_app(ctx, case_id):
    from clarte360_cp.ui.preparation_rc3 import render_builder
    render_builder(ctx, case_id)


def _beneficiary_app(ctx, case_id):
    from clarte360_cp.ui.preparation_rc3 import render_beneficiary
    render_beneficiary(ctx, case_id)


@pytest.fixture
def ui_case(engine, Session, monkeypatch, tmp_path):
    # Même point d'entrée que l'UI ; seule l'adresse de base est isolée.
    monkeypatch.setattr("clarte360_cp.repositories.db.DATABASE_URL", str(engine.url))
    for name in ("DB_DIR", "OBJECTS_DIR", "OUTBOX_DIR", "RECEIPTS_DIR", "RUNTIME_CACHE_DIR", "QUARANTINE_DIR", "TEMP_DIR"):
        monkeypatch.setattr("clarte360_cp.framework.config."+name, tmp_path/name.lower())
    coach=context(scopes=ACC, actor="ACC-RC3C-UI")
    beneficiary=context(role="BENEFICIAIRE", scopes=BEN, actor="BEN-RC3C-UI")
    with Session() as session:
        case_id=CaseRepository(session).open_or_create(coach).case_id
    return str(engine.url), case_id, coach, beneficiary


def _visible_text(app):
    return "\n".join(str(element.value) for name in (
        "markdown", "caption", "info", "warning", "success", "error",
    ) for element in getattr(app, name))


def _label(elements, label):
    return next(element for element in elements if element.label==label)


def test_second_piste_saved_in_place_then_previewed_published_and_rendered(ui_case):
    db, case_id, coach, beneficiary=ui_case
    source={"APS_OBJECTIF":{"authorized":True, "source_ref":"APS-UI-FICTIF",
                            "idea_list":["Métier fictif A", "Métier fictif B", "Métier fictif C"]}}
    draft=create_questionnaire_v2(coach, case_id, source, database_url=db)
    original_ids=[item["id"] for item in draft.questionnaire["ideas_active"]]
    question="Pour ce deuxième métier fictif, souhaitez-vous explorer le cadre associatif ?"
    private_note="NOTE PRIVÉE FICTIVE — information réservée à l'accompagnateur."
    choices="Dans une association fictive\nJe souhaite en discuter en séance"

    app=AppTest.from_function(_builder_app, args=(coach, case_id), default_timeout=10).run()
    assert not app.exception
    app.selectbox[0].set_value(original_ids[1]).run()
    _label(app.text_area, "Remarque privée de l'accompagnateur — non visible par le bénéficiaire").set_value(private_note)
    _label(app.text_area, "Question 6 — contexte d'exercice, visible par le bénéficiaire").set_value(question)
    _label(app.text_area, "Réponses proposées à la question 6 (une par ligne)").set_value(choices)
    _label(app.button, "Enregistrer la fiche de cette piste").click().run()
    assert not app.exception and not app.error
    saved=read_preparation(coach, case_id, database_url=db)
    assert [item["id"] for item in saved.questionnaire["ideas_active"]]==original_ids
    assert saved.questionnaire["ideas_active"][1]["context_prompt"]==question
    assert saved.questionnaire["ideas_active"][1]["context_note"]==private_note
    assert read_preparation(beneficiary, case_id, database_url=db).questionnaire is None

    app.radio(key=f"rc3_coach_nav_{case_id}").set_value("03 — Voir Q complet").run()
    assert not app.exception
    assert question in _visible_text(app)
    assert private_note not in _visible_text(app)
    assert app.expander[1].label.startswith("Piste 2 — Métier fictif B")
    assert question in "\n".join(element.value for element in app.expander[1].markdown)

    app.radio(key=f"rc3_coach_nav_{case_id}").set_value("04 — Verrouiller Q").run()
    _label(app.checkbox, "J'ai relu les questions C-AV1 et C-AV2 et je valide ce questionnaire unique.").check().run()
    _label(app.button, "Valider définitivement et mettre à disposition (C-AV1 + C-AV2)").click().run()
    assert not app.exception and not app.error
    locked=read_preparation(coach, case_id, database_url=db)
    public=read_preparation(beneficiary, case_id, database_url=db)
    assert locked.questionnaire_locked and public.invitation_open
    assert public.questionnaire["ideas_active"][1]["context_prompt"]==question
    assert public.questionnaire["ideas_active"][1]["context_choices"]==choices.splitlines()
    assert all(not item["context_note"] for item in public.questionnaire["ideas_active"])
    assert question in _visible_text(app)  # aperçu conservé après verrouillage
    assert private_note not in _visible_text(app)
    assert not app.text_area

    attempted=copy.deepcopy(locked.questionnaire)
    attempted["ideas_active"][1]["context_prompt"]="Modification interdite après publication"
    with pytest.raises(ValueError, match="verrouillé"):
        save_questionnaire(coach, case_id, attempted,
                           expected_row_version=locked.row_version, database_url=db)

    benef=AppTest.from_function(_beneficiary_app, args=(beneficiary, case_id), default_timeout=10).run()
    assert not benef.exception
    assert question in _visible_text(benef)
    assert private_note not in _visible_text(benef)
    instruction=("Plusieurs réponses possibles. Si vous choisissez Je souhaite préciser, "
                 "utilisez la zone Autres informations sur cette piste ou son contexte, "
                 "située en bas de cette fiche.")
    assert [element.value for element in benef.caption].count(instruction)==3
    assert sum(element.label=="Autres informations sur cette piste ou son contexte (facultatif)"
               for element in benef.text_area)==3
    assert all(benef.text_area(key=f"B_{case_id}_other_{idea_id}").disabled for idea_id in original_ids)
    # Les questions sont lisibles avant Q1 ; la saisie s'active immédiatement
    # après un choix personnel, sans retour arrière et sans présélection.
    assert all(benef.radio(key=f"B_{case_id}_interest_{idea_id}").value is None for idea_id in original_ids)
    benef.radio(key=f"B_{case_id}_interest_{original_ids[1]}").set_value("EXPLORER").run()
    assert not benef.exception
    assert not benef.text_area(key=f"B_{case_id}_other_{original_ids[1]}").disabled
    benef.text_area(key=f"B_{case_id}_other_{original_ids[1]}").set_value("Ma précision fictive pour la deuxième piste").run()
    persisted=read_preparation(beneficiary, case_id, database_url=db).responses
    assert persisted["cav1"]["ideas"][0]["id"]==original_ids[1]
    assert persisted["cav1"]["ideas"][0]["context"]["other"]=="Ma précision fictive pour la deuxième piste"
    assert not persisted["cav1_done"]


def test_final_transmission_requires_saved_visible_answers_and_fresh_confirmation(ui_case):
    db, case_id, coach, beneficiary=ui_case
    draft=create_questionnaire_v2(coach, case_id, {}, database_url=db)
    lock_and_publish_questionnaire(coach, case_id,
                                  expected_row_version=draft.row_version, database_url=db)
    app=AppTest.from_function(_beneficiary_app, args=(beneficiary, case_id), default_timeout=10).run()
    assert not app.exception
    app.checkbox(key=f"B_{case_id}_no_idea").check().run()
    app.button(key=f"rc3_benef_cav1_next_{case_id}").click().run()
    app.text_area(key=f"B_{case_id}_free_valeurs").set_value("Autonomie fictive")
    app.text_area(key=f"B_{case_id}_free_moteurs").set_value("Apprendre dans ce cas fictif")
    app.text_area(key=f"B_{case_id}_pref_free").set_value("Un cadre fictif coopératif")
    app.radio(key=f"B_{case_id}_situation").set_value("NON").run()
    app.button(key=f"rc3_benef_cav2_done_{case_id}").click().run()
    assert not app.exception and not app.error
    confirm_key=f"rc3_benef_confirm_{case_id}"
    submit_key=f"rc3_benef_submit_{case_id}"
    app.checkbox(key=confirm_key).check().run()
    assert not app.button(key=submit_key).disabled

    # Le clic de confirmation précédent ne doit plus autoriser une ancienne R1.
    app.text_area(key=f"B_{case_id}_note_valeurs").set_value("Précision fictive ajoutée après enregistrement").run()
    assert not app.exception
    assert not any(element.key==submit_key and not element.disabled for element in app.button)
    assert app.session_state[confirm_key] is False
    saved_edit=read_preparation(beneficiary, case_id, database_url=db)
    assert saved_edit.active_answers is None
    assert saved_edit.responses["cav2"]["valeurs"]["note"]=="Précision fictive ajoutée après enregistrement"
    assert not saved_edit.responses["cav2_done"]

    # Revenir au texte enregistré n'autorise pas la confirmation antérieure.
    app.text_area(key=f"B_{case_id}_note_valeurs").set_value("").run()
    assert app.session_state[confirm_key] is False
    assert not any(element.key==submit_key and not element.disabled for element in app.button)

    # Des espaces périphériques sont normalisés par le service d'enregistrement.
    last_note="Dernière précision fictive à transmettre"
    app.text_area(key=f"B_{case_id}_note_valeurs").set_value("  "+last_note+"  ").run()
    app.button(key=f"rc3_benef_cav2_done_{case_id}").click().run()
    assert not app.exception and not app.error
    assert not app.checkbox(key=confirm_key).value
    assert app.button(key=submit_key).disabled
    app.checkbox(key=confirm_key).check().run()
    app.button(key=submit_key).click().run()
    assert not app.exception and not app.error
    received=read_preparation(coach, case_id, database_url=db)
    assert received.active_answers["cav2"]["valeurs"]["note"]==last_note
    assert received.active_answers["cav1_done"] and received.active_answers["cav2_done"]
    assert any("ont été transmises" in element.value for element in app.success)


def test_final_confirmation_available_with_published_fictitious_report_results(ui_case):
    db, case_id, coach, beneficiary=ui_case
    draft=create_questionnaire_v2(coach, case_id, synthetic_sources("two"), database_url=db)
    published=lock_and_publish_questionnaire(coach, case_id,
                                            expected_row_version=draft.row_version, database_url=db)
    answers=filled(published.questionnaire)
    answers["cav1_done"]=True
    saved=save_beneficiary_answers(beneficiary, case_id, answers,
                                   expected_row_version=published.row_version, database_url=db)
    answers["cav2_done"]=True
    save_beneficiary_answers(beneficiary, case_id, answers,
                            expected_row_version=saved.row_version, database_url=db)
    app=AppTest.from_function(_beneficiary_app, args=(beneficiary, case_id), default_timeout=10).run()
    assert not app.exception and not app.error
    assert app.checkbox(key=f"rc3_benef_confirm_{case_id}").value is False
    assert app.button(key=f"rc3_benef_submit_{case_id}").disabled
    assert len(app.dataframe)==5


def test_last_cav2_text_is_saved_before_return_and_survives_new_session(ui_case):
    db, case_id, coach, beneficiary=ui_case
    draft=create_questionnaire_v2(coach, case_id, {}, database_url=db)
    published=lock_and_publish_questionnaire(coach, case_id,
                                            expected_row_version=draft.row_version, database_url=db)
    answers=empty_answers_v2(published.questionnaire)
    answers["cav1"]["no_idea"]=True
    answers["cav1_done"]=True
    save_beneficiary_answers(beneficiary, case_id, answers,
                            expected_row_version=published.row_version, database_url=db)
    app=AppTest.from_function(_beneficiary_app, args=(beneficiary, case_id), default_timeout=10).run()
    last_text="Dernier texte fictif saisi juste avant le retour"
    app.text_area(key=f"B_{case_id}_note_valeurs").set_value(last_text)
    app.button(key=f"rc3_back_{case_id}").click().run()
    assert not app.exception and not app.error
    saved=read_preparation(beneficiary, case_id, database_url=db)
    assert saved.responses["cav2"]["valeurs"]["note"]==last_text
    assert not saved.responses["cav2_done"]
    assert any("Étape 1/2" in element.value for element in app.markdown)

    reopened=AppTest.from_function(_beneficiary_app, args=(beneficiary, case_id), default_timeout=10).run()
    assert not reopened.exception
    assert reopened.text_area(key=f"B_{case_id}_note_valeurs").value==last_text


def test_stale_window_keeps_its_text_without_overwrite_until_explicit_reload(ui_case):
    db, case_id, coach, beneficiary=ui_case
    draft=create_questionnaire_v2(coach, case_id, {}, database_url=db)
    lock_and_publish_questionnaire(coach, case_id,
                                  expected_row_version=draft.row_version, database_url=db)
    stale=AppTest.from_function(_beneficiary_app, args=(beneficiary, case_id), default_timeout=10).run()
    other=AppTest.from_function(_beneficiary_app, args=(beneficiary, case_id), default_timeout=10).run()
    other.checkbox(key=f"B_{case_id}_no_idea").check().run()
    saved_elsewhere=read_preparation(beneficiary, case_id, database_url=db)
    assert saved_elsewhere.responses["cav1"]["no_idea"]

    stale_text="Piste fictive saisie dans la fenêtre devenue ancienne"
    stale.text_area(key=f"B_{case_id}_new").set_value(stale_text).run()
    assert not stale.exception
    assert any("autre onglet" in element.value for element in stale.error)
    assert stale.text_area(key=f"B_{case_id}_new").value==stale_text
    assert stale.button(key=f"rc3_benef_cav1_next_{case_id}").disabled
    # Un nouveau clic ne relance pas une écriture sur la base devenue ancienne.
    stale.text_area(key=f"B_{case_id}_new").set_value(stale_text+" — à conserver à l'écran").run()
    assert not stale.exception
    unchanged=read_preparation(beneficiary, case_id, database_url=db)
    assert unchanged.row_version==saved_elsewhere.row_version
    assert unchanged.responses==saved_elsewhere.responses

    stale.button(key=f"rc3_reload_{case_id}").click().run()
    assert not stale.exception and not stale.error
    assert stale.text_area(key=f"B_{case_id}_new").value==""
    assert stale.checkbox(key=f"B_{case_id}_no_idea").value
    assert not stale.button(key=f"rc3_benef_cav1_next_{case_id}").disabled
