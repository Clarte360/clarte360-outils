#!/usr/bin/env python3
"""One-call France Travail ROME Fiches métiers smoke test; never prints secrets."""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from clarte360_cp.connectors.france_travail import (
    FranceTravailConfigurationError,
    FranceTravailError,
    FranceTravailRomeClient,
    FranceTravailSettings,
)

DEFAULT_SECRETS = Path("/opt/clarte360/secrets/secrets.toml")


def _title(payload: dict) -> str:
    for candidate in (payload, payload.get("fiche_metier"), payload.get("rome")):
        if isinstance(candidate, dict):
            for key in ("intitule", "libelle", "title"):
                value = candidate.get(key)
                if value:
                    return str(value)[:240]
            nested = candidate.get("rome")
            if isinstance(nested, dict):
                for key in ("intitule", "libelle", "title"):
                    value = nested.get(key)
                    if value:
                        return str(value)[:240]
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Teste une fiche ROME France Travail sans afficher d’identifiant, secret ou jeton."
    )
    parser.add_argument("--code", default="M1203", help="Code ROME à vérifier (par défaut : M1203)")
    parser.add_argument("--scope", help="Scope ROME Fiches métiers affiché dans le portail (paramètre non secret)")
    parser.add_argument("--secrets", type=Path, default=DEFAULT_SECRETS, help=argparse.SUPPRESS)
    args = parser.parse_args()

    try:
        with args.secrets.open("rb") as handle:
            config = tomllib.load(handle)
        section = config.get("france_travail", {})
        if not isinstance(section, dict):
            section = {}
        section = dict(section)
        if args.scope:
            section["rome_fiches_metiers_scope"] = args.scope
        settings = FranceTravailSettings.from_mapping(section)
        result = FranceTravailRomeClient(settings).fetch_fiche_metier(args.code, force_refresh=True)
    except PermissionError:
        print("TEST: BLOQUÉ — lecture du fichier central refusée")
        return 2
    except FileNotFoundError:
        print("TEST: BLOQUÉ — fichier central introuvable")
        return 2
    except (tomllib.TOMLDecodeError, FranceTravailConfigurationError):
        print("TEST: BLOQUÉ — configuration centrale incomplète ou invalide (aucune valeur affichée)")
        return 2
    except ValueError as exc:
        print(f"TEST: BLOQUÉ — {exc}")
        return 2
    except FranceTravailError as exc:
        print(f"TEST: ÉCHEC — {exc}")
        return 1
    except Exception:
        print("TEST: ÉCHEC — erreur inattendue (détails masqués pour protéger la configuration)")
        return 1

    print("Authentification OAuth et appel ROME Fiches métiers: OK")
    print(f"Code ROME: {result.code}")
    title = _title(dict(result.payload))
    if title:
        print(f"Intitulé reçu: {title}")
    print(f"Date de récupération UTC: {result.fetched_at.isoformat()}")
    print(f"Version du référentiel: {result.source_version or 'non fournie dans la réponse'}")
    print(f"ETag: {result.source_etag or 'non fourni dans la réponse'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
