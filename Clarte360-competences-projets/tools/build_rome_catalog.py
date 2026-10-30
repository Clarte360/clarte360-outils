from __future__ import annotations

import argparse
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


VERSION = "ROME 4.0 version 61 (26M06)"
PUBLICATION_DATE = "2026-06-15"


def _node_value(node: ET.Element):
    children = list(node)
    if not children:
        return (node.text or "").strip()
    result = {}
    for child in children:
        value = _node_value(child)
        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(value)
        else:
            result[child.tag] = value
    return result


def build(source_zip: Path, *, version: str | None = None,
          publication_date: str | None = None) -> dict:
    with zipfile.ZipFile(source_zip) as archive:
        files = [name for name in archive.namelist()
                 if re.fullmatch(r"unix_fiche_emploi_metier_v\d+_[^/]+\.xml", name)]
        if len(files) != 1:
            raise ValueError("L’archive doit contenir exactement un export XML de fiches ROME.")
        xml_name = files[0]
        match = re.search(r"_v(\d+)_", xml_name)
        assert match
        source_version = match.group(1)
        if version is None or publication_date is None:
            if source_version != "461":
                raise ValueError("Renseignez --version et --publication-date à partir des métadonnées de l’export officiel.")
            version = version or VERSION
            publication_date = publication_date or PUBLICATION_DATE
        root = ET.fromstring(archive.read(xml_name))
    entries = []
    seen = set()
    for fiche in root.findall("fiche_metier"):
        data = _node_value(fiche)
        rome = data.get("rome", {})
        code = str(rome.get("code_rome", "")).strip().upper()
        label = str(rome.get("intitule", "")).strip()
        if not re.fullmatch(r"[A-Z]\d{4}", code) or not label:
            raise ValueError("L’export contient une fiche sans code ROME ou intitulé exploitable.")
        if code in seen:
            raise ValueError(f"Code ROME en doublon dans l’export : {code}.")
        if not data.get("definition") or not data.get("acces_metier"):
            raise ValueError(f"La fiche {code} ne contient pas sa définition et son bloc d’accès descriptif.")
        if not isinstance(data.get("competences"), dict) or not data["competences"]:
            raise ValueError(f"La fiche {code} ne contient pas de bloc de compétences exploitable.")
        if not data.get("contextes_travail"):
            raise ValueError(f"La fiche {code} ne contient pas de contexte de travail exploitable.")
        seen.add(code)
        entries.append({
            "code": code,
            "intitule": label,
            "numero": str(data.get("numero", "")),
            "definition": data.get("definition", ""),
            "acces_metier": data.get("acces_metier", ""),
            "appellations": data.get("appellations", {}),
            "competences": data.get("competences", {}),
            "contextes_travail": data.get("contextes_travail", {}),
        })
    entries.sort(key=lambda row: (row["code"], row["intitule"].casefold()))
    return {
        "version": version,
        "publication_date": publication_date,
        "source_file": f"{source_zip.name} / {xml_name}",
        "entry_count": len(entries),
        "items": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the compact offline ROME métier catalog.")
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", help="Version officielle affichée dans les métadonnées de l’export.")
    parser.add_argument("--publication-date", help="Date officielle de publication (AAAA-MM-JJ).")
    args = parser.parse_args()
    if args.version and not args.version.strip():
        parser.error("--version ne peut pas être vide.")
    if args.publication_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.publication_date):
        parser.error("--publication-date doit être au format AAAA-MM-JJ.")
    catalog = build(args.source_zip, version=args.version, publication_date=args.publication_date)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(catalog['items'])} fiches ROME écrites dans {args.output}")


if __name__ == "__main__":
    main()
