from __future__ import annotations

import zipfile

import pytest

from tools.build_rome_catalog import build
from tools.compare_rome_catalog_update import compare


def _write_export(path, *, version="462", codes=("M1203", "K1201")):
    rows = []
    for index, code in enumerate(codes, start=1):
        rows.append(f"""
        <fiche_metier>
          <numero>{index}</numero>
          <rome><code_rome>{code}</code_rome><intitule>Intitulé {code}</intitule></rome>
          <definition>Définition métier {code}</definition>
          <acces_metier>Accès descriptif {code}</acces_metier>
          <appellations><appellation><libelle>Appellation {code}</libelle></appellation></appellations>
          <competences><savoirs><categories><categorie><libelle>Domaine</libelle></categorie></categories></savoirs></competences>
          <contextes_travail><type_contexte><libelle>Conditions</libelle></type_contexte></contextes_travail>
        </fiche_metier>""")
    document = '<?xml version="1.0" encoding="ISO-8859-15"?><referentiel>' + "".join(rows) + "</referentiel>"
    member = f"unix_fiche_emploi_metier_v{version}_iso8859-15.xml"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, document.encode("iso-8859-15"))
    return path


def test_builder_accepts_versioned_official_export_and_requires_metadata(tmp_path):
    source = _write_export(tmp_path / "RefRomeXml.zip")
    with pytest.raises(ValueError, match="Renseignez --version"):
        build(source)
    catalog = build(source, version="ROME 4.0 version 62", publication_date="2026-10-01")
    assert catalog["version"] == "ROME 4.0 version 62"
    assert catalog["publication_date"] == "2026-10-01"
    assert catalog["entry_count"] == 2
    assert catalog["source_file"].endswith("unix_fiche_emploi_metier_v462_iso8859-15.xml")


def test_comparison_reports_added_removed_and_changed_codes():
    old = {"version": "v61", "publication_date": "2026-06-15", "items": [
        {"code": "M1203", "intitule": "Comptable", "competences": {"savoirs": ["A"]}},
        {"code": "K1201", "intitule": "Autre métier", "competences": {"savoirs": ["B"]}},
    ]}
    new = {"version": "v62", "publication_date": "2026-10-01", "items": [
        {"code": "M1203", "intitule": "Comptable", "competences": {"savoirs": ["A", "B"]}},
        {"code": "K1202", "intitule": "Nouveau métier", "competences": {"savoirs": ["C"]}},
    ]}
    report = compare(old, new)
    assert report["added_codes"] == ["K1202"]
    assert report["removed_codes"] == ["K1201"]
    assert report["changed_codes"] == ["M1203"]

