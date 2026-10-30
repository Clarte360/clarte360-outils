"""Create an isolated, fully synthetic GO22 ROME / investigation demo database.

The destination database must not already exist. Never point this tool at a
production or participant database. It prints temporary 15-minute launch
tokens for the two demo roles; it does not read or write Streamlit secrets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories import build_engine, init_database, session_factory
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import CareerItem, ExternalSnapshot, IntersessionTask, JobTarget
from tools.go21_demo_seed import context, token


ROME_FICHE_SYNTHETIQUE = {
    "code_rome": "M1203",
    "intitule": "Comptable — métier fictif de recette",
    "version": "ROME_SYNTHETIQUE_GO22",
    "competences": {
        "savoirs": {"categories": [{"libelle": "Gestion comptable", "items": [
            {"libelle": "Comptabilité générale", "code_ogr": "SYNTH-117781"},
            {"libelle": "Comptabilité clients", "code_ogr": "SYNTH-117782"},
        ]}]},
        "savoir_faire": {"enjeux": [{"libelle": "Gestion des comptes", "items": [
            {"libelle": "Réaliser les opérations comptables", "code_ogr": "SYNTH-117783"},
        ]}]},
    },
}


def build_demo(db_path: str | Path, signing_key: str) -> dict[str, str]:
    path = Path(db_path).expanduser().resolve()
    if path.exists():
        raise FileExistsError("La base de recette existe déjà ; choisissez un nouveau chemin temporaire.")
    if not signing_key or len(signing_key) < 32:
        raise ValueError("Fournissez une clé fictive de recette d’au moins 32 caractères.")
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = build_engine(f"sqlite:///{path}")
    init_database(engine)
    factory = session_factory(engine)
    coach = context(ActorRole.ACCOMPAGNATEUR)
    beneficiary = context(ActorRole.BENEFICIAIRE)
    payload_json = json.dumps(ROME_FICHE_SYNTHETIQUE, ensure_ascii=False, separators=(",", ":"))
    with factory() as session:
        case = CaseRepository(session).open_or_create(coach)
        snapshot = ExternalSnapshot(
            case_id=case.case_id, provider="SYNTHETIQUE", resource_type="ROME_FICHE_METIER",
            external_key="M1203", payload_json=payload_json,
            sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(), effective_date="2026-10-23",
        )
        session.add(snapshot)
        session.flush()
        target = JobTarget(
            case_id=case.case_id, rome_code="M1203", rome_label="Comptable — métier fictif de recette",
            snapshot_id=snapshot.snapshot_id, status="ACTIVE", selected_order=1,
        )
        session.add_all([
            target,
            CareerItem(
                case_id=case.case_id, item_type="EMPLOI", title="Aide comptable — situation fictive",
                details_json=json.dumps({"activities": "Classement de pièces, lettrage de comptes clients, rapprochement de règlements.",
                                         "provenance": "SIMULATION_SYNTHETIQUE"}, ensure_ascii=False),
                status="ACTIVE",
            ),
            CareerItem(
                case_id=case.case_id, item_type="ETUDE", title="Études de comptabilité sans diplôme — fictives",
                details_json=json.dumps({"activities": "Étude du plan comptable et exercices sur les écritures courantes.",
                                         "provenance": "SIMULATION_SYNTHETIQUE"}, ensure_ascii=False),
                status="ACTIVE",
            ),
            CareerItem(
                case_id=case.case_id, item_type="FORMATION", title="Initiation à un logiciel comptable — fictive",
                details_json=json.dumps({"activities": "Saisie d'écritures et édition d'une balance sur un environnement pédagogique.",
                                         "provenance": "SIMULATION_SYNTHETIQUE"}, ensure_ascii=False),
                status="ACTIVE",
            ),
            IntersessionTask(
                case_id=case.case_id, task_type="OFFRES_EMPLOI", state="PUBLIEE",
                question_or_goal="Comparer deux offres fictives et relever les compétences demandées ainsi que les conditions d’accès mentionnées.",
                version_no=1, created_by=coach.actor_id,
            ),
        ])
        case_id = case.case_id
        session.commit()
    return {
        "case_id": case_id,
        "accompagnateur_token": token(coach, signing_key),
        "beneficiaire_token": token(beneficiary, signing_key),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Base temporaire fictive pour la prévisualisation GO22 ROME.")
    parser.add_argument("--db", required=True, help="Nouveau chemin SQLite temporaire (refus si le fichier existe).")
    parser.add_argument("--signing-key", required=True, help="Clé fictive temporaire, jamais un secret VPS.")
    args = parser.parse_args()
    result = build_demo(args.db, args.signing_key)
    print(f"DEMO_CASE_ID={result['case_id']}")
    print(f"ACCOMPAGNATEUR_TOKEN={result['accompagnateur_token']}")
    print(f"BENEFICIAIRE_TOKEN={result['beneficiaire_token']}")


if __name__ == "__main__":
    main()
