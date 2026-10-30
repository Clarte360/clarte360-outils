#!/usr/bin/env python3
"""Run one bounded live smoke check for each subscribed ROME 4.0 product.

Reads the existing central Streamlit France Travail settings. It prints no
credential, token, response body, or personal data. All requests use the
synthetic ROME example M1203 and one competence/context code from the packaged
official snapshot; no beneficiary or case data is read or written.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping

from clarte360_cp.connectors.france_travail import (
    FranceTravailError,
    FranceTravailRomeClient,
    FranceTravailSettings,
)


def _first_ogr_code(value: Any) -> str | None:
    if isinstance(value, dict):
        code = value.get("code_ogr")
        if code is not None and str(code).isdigit():
            return str(code)
        for child in value.values():
            found = _first_ogr_code(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _first_ogr_code(child)
            if found:
                return found
    return None


def _metadata(snapshot) -> tuple[str, str]:
    payload = snapshot.payload
    for container in (payload, payload.get("rome"), payload.get("metier"), payload.get("competence"), payload.get("contexte")):
        if isinstance(container, dict):
            label = next((str(container[key]).strip() for key in ("intitule", "libelle", "label", "nom")
                          if isinstance(container.get(key), str) and container[key].strip()), "réponse reçue")
            version = next((str(container[key]) for key in ("version", "versionReferentiel", "version_referentiel")
                            if container.get(key) is not None), "non fournie")
            return label[:160], version[:80]
    return "réponse reçue", snapshot.source_version or "non fournie"


def _settings() -> FranceTravailSettings:
    try:
        import streamlit as st
        section = st.secrets.get("france_travail", {})
    except Exception:
        section = {}
    if not isinstance(section, Mapping):
        raise RuntimeError("Configuration France Travail indisponible dans ce processus.")
    return FranceTravailSettings.from_mapping(section)


def main() -> int:
    catalog_path = Path(__file__).resolve().parents[1] / "clarte360_cp" / "data" / "rome_catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        fiche = next(row for row in catalog["items"] if row.get("code") == "M1203")
        competence_code = _first_ogr_code(fiche.get("competences"))
        context_code = _first_ogr_code(fiche.get("contextes_travail"))
        if not competence_code or not context_code:
            raise ValueError("Codes synthétiques de référence introuvables dans le corpus local.")
        client = FranceTravailRomeClient(_settings())
    except Exception as exc:
        print(f"ÉCHEC PRÉPARATION — {type(exc).__name__}: {exc}")
        return 2

    checks = (
        ("ROME Métiers", lambda: client.fetch_metier("M1203", force_refresh=True)),
        ("ROME recherche métiers/appellations", lambda: client.search_metiers("comptable", limit=5)),
        ("ROME Compétences", lambda: client.fetch_competence(competence_code, force_refresh=True)),
        ("ROME Contextes de travail", lambda: client.fetch_contexte(context_code, force_refresh=True)),
        ("ROME Fiches métiers", lambda: client.fetch_fiche_metier("M1203", force_refresh=True)),
    )
    failures = 0
    for index, (label, call) in enumerate(checks):
        if index:
            # Public ROME products announce a limit of one API call per second.
            time.sleep(1.1)
        try:
            result = call()
            if isinstance(result, tuple):
                if not result:
                    raise ValueError("Aucun métier ou appellation ne correspond au terme de contrôle.")
                first = result[0]
                print(f"OK — {label} — {len(result)} résultat(s) — {first['code']} — {first['label']}")
            else:
                title, version = _metadata(result)
                print(f"OK — {label} — {result.code} — {title} — version {version} — {result.fetched_at.isoformat()} — ETag {result.source_etag or 'non fourni'}")
        except (FranceTravailError, ValueError) as exc:
            failures += 1
            print(f"ÉCHEC — {label} — {exc}")
    print(f"Résultat : {len(checks) - failures}/{len(checks)} produits ROME vérifiés. Aucun dossier bénéficiaire utilisé.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
