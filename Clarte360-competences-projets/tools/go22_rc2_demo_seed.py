"""Dossier de recette SYNTHETIQUE C-AV1/C-AV2 : aucun document client.

Ne fait aucun appel IA, SMTP, GDA ou action VPS. Les jetons ont TTL <= 900 s.
Le lanceur GO21 construit les deux roles et les douze ecrans historiques.
"""
from __future__ import annotations

import argparse
import sys

from clarte360_cp.application.preparation import (
    confirm_joint_review, create_questionnaire, lock_questionnaire,
    open_beneficiary_access, save_beneficiary_answers, save_joint_review,
    submit_beneficiary_answers,
)
from clarte360_cp.domain.preparation import empty_answers
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.cases import CaseRepository
from tools import go21_demo_seed


def sources_synthetiques() -> dict:
    return {
        "APS_OBJECTIF": {"authorized": True, "source_ref": "SYNTH-APS-001",
                         "idea_list": ["scénographie d'exposition", "activité en entreprise familiale"]},
        "BOUSSOLE_VALEURS": {"authorized": True, "source_ref": "SYNTH-BOUSSOLE-001",
                             "items": ["Créativité", "Respect", "Autonomie", "Coopération"]},
        "MOTEURS_PRO": {"authorized": True, "source_ref": "SYNTH-MOTEURS-001"},
        "PREFERENCES_PRO": {"authorized": True, "source_ref": "SYNTH-PREF-001",
                            "items_go": ["Autonomie", "Activités variées", "Travail en équipe"],
                            "items_no_go": ["Micro-management", "Répétition excessive", "Isolement prolongé"]},
        "IPIP_REPORT": {"authorized": True, "source_ref": "SYNTH-NEO-001",
                        "items": ["Temps de réflexion", "Coopération structurée"]},
        "PIP_REPORT": {"authorized": True, "source_ref": "SYNTH-RIASEC-001",
                       "items": ["Concevoir une exposition", "Organiser une activité", "Accueillir le public"]},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Jeu SYNTHETIQUE GO22 RC2 double interface / C-AV1 et C-AV2")
    parser.add_argument("--db", required=True, help="Base locale de recette, ECRASEE par le seed GO21")
    parser.add_argument("--signing-key", required=True, help="Cle FICTIVE pour recette locale uniquement")
    parser.add_argument("--stage", choices=("empty", "ready", "answered", "reviewed"), default="ready")
    args = parser.parse_args()

    old_argv = sys.argv
    try:
        sys.argv = ["go21_demo_seed.py", "--db", args.db, "--signing-key", args.signing_key]
        go21_demo_seed.main()  # construit un dossier purement fictif + affiche les jetons doubles roles
    finally:
        sys.argv = old_argv

    if args.stage == "empty":
        print("ETAPE=VIDE : l'accompagnateur peut generer le questionnaire")
        return

    engine = build_engine(f"sqlite:///{args.db}")
    Factory = session_factory(engine)
    acc = go21_demo_seed.context(ActorRole.ACCOMPAGNATEUR)
    ben = go21_demo_seed.context(ActorRole.BENEFICIAIRE)
    with Factory() as session:
        case = CaseRepository(session).open_or_create(acc)
        case_id = case.case_id
    draft = create_questionnaire(acc, case_id, sources_synthetiques(), context="AUTOFINANCE",
                                 intro="Recette fictive : choisissez librement vos critères, sans IA ni réponse attendue.",
                                 database_url=f"sqlite:///{args.db}")
    locked = lock_questionnaire(acc, case_id, expected_row_version=draft.row_version,
                                database_url=f"sqlite:///{args.db}")
    ready = open_beneficiary_access(acc, case_id, expected_row_version=locked.row_version,
                                    database_url=f"sqlite:///{args.db}")
    if args.stage == "ready":
        print("ETAPE=READY : questionnaire verrouille et visible pour le beneficiaire ; aucune reponse transmise")
        return
    responses = empty_answers(ready.questionnaire)
    responses["ideas"] = [{"wording": "scénographie d'exposition", "meaning": ["Exercer ce métier"],
                           "status": ["Salariat privé"], "attraction": ["Créativité ou innovation"],
                           "access": ["Reste à vérifier"], "note": "Cas entièrement fictif"}]
    for section in ready.questionnaire["sections"]:
        if section["required"]:
            responses["selections"][section["code"]] = section["choices"][:1]
    saved = save_beneficiary_answers(ben, case_id, responses, expected_row_version=ready.row_version,
                                     database_url=f"sqlite:///{args.db}")
    submitted = submit_beneficiary_answers(ben, case_id, expected_row_version=saved.row_version,
                                           database_url=f"sqlite:///{args.db}")
    if args.stage == "answered":
        print("ETAPE=ANSWERED : R1 fictive verrouillee, le professionnel peut la relire")
        return
    import copy
    revised = copy.deepcopy(responses)
    revised["selections"]["VALEURS"] = ["Créativité", "Respect"]
    pending = save_joint_review(acc, case_id, revised, expected_row_version=submitted.row_version,
                                database_url=f"sqlite:///{args.db}")
    confirm_joint_review(acc, case_id, beneficiary_confirmed=True, method="PARTAGE_ECRAN_ORAL",
                         expected_row_version=pending.row_version, database_url=f"sqlite:///{args.db}")
    print("ETAPE=REVIEWED : R1 originale preservee ; R2 fictive revalidee et active")


if __name__ == "__main__":
    main()
