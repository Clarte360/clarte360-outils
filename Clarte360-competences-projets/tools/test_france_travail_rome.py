#!/usr/bin/env python3
"""One-call France Travail ROME smoke test; emits no credential or token."""
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Test réel, ciblé et sans affichage de secret de l'API ROME France Travail.")
    parser.add_argument("--code", default="M1203", help="Code ROME à vérifier (par défaut : M1203)")
    parser.add_argument("--secrets", type=Path, default=DEFAULT_SECRETS, help=argparse.SUPPRESS)
    parser.add_argument("--scope", help="Scope ROME affiché dans le portail France Travail (paramètre non secret)")
    args = parser.parse_args()

    try:
        with args.secrets.open("rb") as handle:
            config = tomllib.load(handle)
        section = config.get("france_travail", {})
        if not isinstance(section, dict):
            section = {}
        section = dict(section)
        if args.scope:
            section["rome_scope"] = args.scope
        settings = FranceTravailSettings.from_mapping(section)
        result = FranceTravailRomeClient(settings).fetch_metier(args.code)
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
        # Unexpected provider/client errors are intentionally redacted.
        print("TEST: ÉCHEC — erreur inattendue (détails masqués pour protéger la configuration)")
        return 1

    title = result.payload.get("intitule") or result.payload.get("libelle") or result.payload.get("title")
    print("Authentification OAuth: OK")
    print("Appel API ROME Métiers: OK")
    print(f"Code ROME: {result.code}")
    if title:
        print(f"Intitulé reçu: {str(title)[:240]}")
    print(f"Date de récupération UTC: {result.fetched_at.isoformat()}")
    print(f"Version du référentiel: {result.source_version or 'non fournie dans la réponse'}")
    print(f"ETag: {result.source_etag or 'non fourni dans la réponse'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
