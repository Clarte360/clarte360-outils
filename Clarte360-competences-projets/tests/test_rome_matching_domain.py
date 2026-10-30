from __future__ import annotations

import pytest

from clarte360_cp.domain.rome_matching import rome_study_items, validate_review_rows


def fiche_payload():
    return {
        "code_rome": "M1203",
        "intitule": "Comptable",
        "competences": {
            "savoir_faire": {"enjeux": [{"libelle": "Gestion comptable", "items": [
                {"libelle": "Contrôler les écritures comptables", "code_ogr": "522240"},
            ]}]},
            "savoir_etre_professionnel": {"enjeux": [{"libelle": "Coopération", "items": [
                {"libelle": "Faire preuve de rigueur et de précision", "code_ogr": "300490"},
            ]}]},
            "savoirs": {"categories": [{"libelle": "Domaines d’expertise", "items": [
                {"libelle": "Comptabilité client", "code_ogr": "117781"},
            ]}]},
        },
        "acces_metier": "Cette donnée ne constitue pas un diplôme obligatoire.",
    }


def test_extracts_only_actual_rome_skill_categories_and_stable_codes():
    items = rome_study_items(fiche_payload())
    assert len(items) == 3
    assert {item.category for item in items} == {"SAVOIR", "SAVOIR_FAIRE", "SAVOIR_ETRE"}
    assert {item.key for item in items} == {"SAVOIR:117781", "SAVOIR_FAIRE:522240", "SAVOIR_ETRE:300490"}
    assert all("obligatoire" not in item.label.casefold() for item in items)


def test_supports_camel_case_api_fields_and_deduplicates():
    payload = {"competences": {"savoirFaire": [{"libelle": "Gérer les comptes", "codeOgr": "A1"},
                                               {"libelle": "Gérer les comptes", "codeOgr": "A1"}]}}
    items = rome_study_items(payload)
    assert [(x.key, x.category) for x in items] == [("SAVOIR_FAIRE:A1", "SAVOIR_FAIRE")]


def test_handles_nested_rome_v4_categories_and_items_shape():
    payload = {"competences": {
        "savoir_faire": {"enjeux": {"enjeu": {"libelle": "Gestion comptable", "items": {
            "item": [{"libelle": "Contrôler les écritures comptables", "code_ogr": "522240"}]
        }}}},
        "savoirs": {"categories": {"categorie": {"libelle": "Domaines d’expertise", "items": {
            "item": [{"libelle": "Comptabilité client", "code_ogr": "117781"}]
        }}}},
    }}
    items = rome_study_items(payload)
    assert {item.key for item in items} == {"SAVOIR_FAIRE:522240", "SAVOIR:117781"}


def test_acquis_requires_experience_and_all_references_must_be_known():
    valid = {"SAVOIR:117781"}
    with pytest.raises(ValueError, match="expérience"):
        validate_review_rows([{"rome_item_key": "SAVOIR:117781", "status": "ACQUIS_ETAYE",
                               "experience_ids": [], "rationale": ""}], valid, {"experience-1"})
    with pytest.raises(ValueError, match="expérience choisie"):
        validate_review_rows([{"rome_item_key": "SAVOIR:117781", "status": "A_CONFIRMER",
                               "experience_ids": ["other"], "rationale": ""}], valid, {"experience-1"})
    with pytest.raises(ValueError, match="niveau d’exercice discuté"):
        validate_review_rows([{"rome_item_key": "SAVOIR:117781", "status": "ACQUIS_ETAYE",
                               "experience_ids": ["experience-1"], "rationale": ""}], valid, {"experience-1"})
    accepted = validate_review_rows([{"rome_item_key": "SAVOIR:117781", "status": "ACQUIS_ETAYE",
        "experience_ids": ["experience-1"], "rationale": "", "exercise_level": 2}], valid, {"experience-1"})
    assert accepted[0]["exercise_level"] == 2
