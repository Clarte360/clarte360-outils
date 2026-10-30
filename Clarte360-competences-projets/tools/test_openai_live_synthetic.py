"""Live smoke test for the three Clarté360 AI flows using synthetic data only.

Run from the candidate root in the same environment as Streamlit secrets. The
script never prints the API key and never loads a real case or CV.
"""
from __future__ import annotations

import argparse
import json
import sys

from clarte360_cp.connectors.cav3_ai import Cav3AIError, Cav3AISettings, analyze_cav3
from clarte360_cp.connectors.cv_enrichment_ai import analyze_cv_text
from clarte360_cp.connectors.rome_matching_ai import analyze_rome_matching


SYNTHETIC_CAV3 = {
    "schema": "GO22_CAV3_INPUT_V1",
    "response_version": 1,
    "response_sha256": "a" * 64,
    "reponses": {
        "schema": "GO22_CAV1_CAV2_REPONSES_UNIQUES_V2",
        "reponses": [
            {"code": "AV1_MOTIVATION", "reponse": "Aimer organiser une activité fictive."},
            {"code": "AV2_PREFERENCE", "reponse": "Préférer préparer son travail avec méthode."},
        ],
    },
    "sources": [{"id": "SYN-APS-1", "nature": "SYNTHETIQUE", "texte": "Piste fictive : coordonner une petite activité."}],
    "evidence": {"SYN-APS-1": ["Coordonner une activité fictive."]},
    "perspective_entreprise": "",
}

SYNTHETIC_CV = (
    "DOCUMENT FICTIF - aucun bénéficiaire réel.\n"
    "Assistante administrative en entreprise fictive, 2022-2025. "
    "Classement de factures, mise à jour de tableaux de suivi, préparation de dossiers. "
    "Formation courte en bureautique; autonomie et résultats à clarifier en séance."
)

SYNTHETIC_JOB = {"rome_code": "M1203", "label": "Comptable (fiche synthétique de recette)"}
SYNTHETIC_ITEMS = [
    {"key": "SAVOIR_FAIRE:TEST-1", "category": "SAVOIR_FAIRE", "label": "Classer des pièces comptables"},
    {"key": "SAVOIR:TEST-2", "category": "SAVOIR", "label": "Connaître les principes de classement comptable"},
]
SYNTHETIC_EXPERIENCES = [
    {"id": "EXP-SYN-1", "kind": "EMPLOI", "title": "Assistante administrative", "period": "2022-2025",
     "evidence": "A classé des factures dans un exercice fictif; le niveau d'autonomie reste à préciser."},
    {"id": "EXP-SYN-2", "kind": "FORMATION", "title": "Initiation bureautique", "period": "2023",
     "evidence": "A étudié l'organisation de fichiers et de tableaux, sans évaluation comptable décrite."},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Test live des connecteurs IA C&P avec des données entièrement fictives.")
    parser.add_argument("--pipeline", choices=("cav3", "cv", "rome"), required=True,
                        help="Un seul pipeline par exécution pour garder l'essai ciblé.")
    args = parser.parse_args()
    try:
        settings = Cav3AISettings.from_streamlit_secrets()
        if args.pipeline == "cav3":
            result = analyze_cav3(SYNTHETIC_CAV3, settings)
        elif args.pipeline == "cv":
            result = analyze_cv_text(SYNTHETIC_CV, settings, source_refs=["SYN-CV-1"])
        else:
            result = analyze_rome_matching(SYNTHETIC_JOB, SYNTHETIC_ITEMS, SYNTHETIC_EXPERIENCES, settings)
    except Cav3AIError as exc:
        print(json.dumps({"pipeline": args.pipeline, "status": "ERROR", "message": str(exc)}, ensure_ascii=False))
        return 2
    except Exception:
        print(json.dumps({"pipeline": args.pipeline, "status": "ERROR", "message": "Le diagnostic IA a échoué sans détail exploitable."}, ensure_ascii=False))
        return 2

    result_body = result.get("result") if args.pipeline in {"cav3", "rome"} else {
        key: value for key, value in result.items() if key != "metadata"
    }
    report = {
        "pipeline": args.pipeline,
        "status": "OK",
        "synthetic_only": True,
        "model": result.get("model"),
        "metadata": result.get("metadata", {}),
        "result": result_body,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
