from clarte360_cp.application import rome_catalog


def test_search_rome_ignores_accents_and_prioritizes_primary_titles(monkeypatch):
    monkeypatch.setattr(rome_catalog, "_local_catalog", lambda: {"items": [
        {"code": "A1111", "intitule": "Assistant de gestion", "appellations": {
            "appellation": [{"libelle": "Comptable assistant"}]}},
        {"code": "M1203", "intitule": "Comptable", "appellations": {
            "appellation": [{"libelle": "Assistant comptable"}]}},
        {"code": "M1204", "intitule": "Comptabilité", "appellations": {"appellation": []}},
    ]})

    rows = rome_catalog.search_local_rome("comptable")
    assert [row["code"] for row in rows] == ["M1203", "A1111"]
    assert rome_catalog.search_local_rome("comptabilite")[0]["code"] == "M1204"


def test_search_rome_exact_code_is_first_and_limit_is_applied_after_ranking(monkeypatch):
    monkeypatch.setattr(rome_catalog, "_local_catalog", lambda: {"items": [
        {"code": "M1204", "intitule": "Comptabilité", "appellations": {"appellation": []}},
        {"code": "M1203", "intitule": "Comptable", "appellations": {"appellation": []}},
    ]})

    rows = rome_catalog.search_local_rome("M1203", limit=1)
    assert rows == ({"code": "M1203", "label": "Comptable"},)
