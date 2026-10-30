"""Recette ISOLEE RC3 : dossier et sources 100% SYNTHETIQUES.

ATTENTION : --db est REINITIALISE par le générateur GO21. Ne jamais utiliser
une base existante de production. Cette CLI est réservée au VPS de recette.
"""
from __future__ import annotations
import argparse
import copy
import sys

from clarte360_cp.application.preparation import (
    create_questionnaire_v2, lock_questionnaire, open_beneficiary_access,
    save_beneficiary_answers, submit_beneficiary_answers, save_joint_review,
    confirm_joint_review,
)
from clarte360_cp.domain.preparation import empty_answers
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.cases import CaseRepository
from tools import go21_demo_seed
from tools.go22_rc3b_fake_evidence import demo_summaries

PREFS = [
    ("Responsabilités","Contribuer sans rôle de pilotage","Coordonner et porter des responsabilités"),
    ("Organisation","S'organiser librement selon les besoins","Planifier et hiérarchiser les priorités"),
    ("Changement","Privilégier les repères connus","Rechercher de la nouveauté et du mouvement"),
    ("Contribution","Soutenir une organisation","Contribuer au développement des personnes"),
    ("Apprentissage","Apprendre dans un cadre accompagné","Apprendre en expérimentant"),
    ("Décision","Rechercher des arbitrages partagés","Décider par analyse structurée"),
    ("Action","Préparer et observer avant d'agir","Agir avec des résultats visibles"),
    ("Relations","Privilégier du travail autonome","Privilégier les échanges et le collectif"),
    ("Autonomie","Préférer un cadre guidé","Préférer une grande liberté de décision"),
    ("Environnement","Apprécier la variété et la mobilité","Préférer calme et stabilité"),
]


def synthetic_sources(scenario="two"):
    ideas = {
        "two": ["Conception d'expositions","Activité dans un commerce de proximité"],
        "zero": [],
        "many": ["Conception d'expositions","Activité dans un commerce de proximité", "Projet associatif", "Gestion d'événements", "Conseil clientèle"],
    }[scenario]
    from clarte360_cp.domain.preparation_v2 import MOTOR_LABELS
    pref_dims=[{"code":f"PP{i+1}","label":label,"pole_1":p1,"pole_2":p2}
        for i,(label,p1,p2) in enumerate(PREFS)]
    val_names=["Créativité","Respect","Autonomie","Coopération","Utilité","Sécurité"]
    summaries=demo_summaries(val_names,list(MOTOR_LABELS),pref_dims)
    return {
        "APS_OBJECTIF":{"authorized":True,"source_ref":"SIMULATION/APS-001","status":"FICTIF","idea_list":ideas},
        "BOUSSOLE_VALEURS":{"authorized":True,"source_ref":"SIMULATION/VAL-001","status":"FICTIF", "items":val_names,"result_summary":summaries["BOUSSOLE_VALEURS"]},
        "MOTEURS_PRO":{"authorized":True,"source_ref":"SIMULATION/MOT-001","status":"FICTIF", "result_summary":summaries["MOTEURS_PRO"]},
        "PREFERENCES_PRO":{"authorized":True,"source_ref":"SIMULATION/PREF-001","status":"FICTIF",
                            "dimensions":pref_dims, "result_summary":summaries["PREFERENCES_PRO"]},
        "IPIP_REPORT":{"authorized":True,"source_ref":"SIMULATION/NEO-001","status":"FICTIF", "result_summary":summaries["IPIP_REPORT"]},
        "PIP_REPORT":{"authorized":True,"source_ref":"SIMULATION/PIP-001","status":"FICTIF", "result_summary":summaries["PIP_REPORT"]},
    }


def filled(q):
    a = empty_answers(q)
    for idx, idea in enumerate(q["ideas_active"]):
        a["cav1"]["ideas"].append({"id":idea["id"], "interest":"EXPLORER" if idx==0 else "INDECISE",
          "meaning":["Exercer une partie de ses activités"],"status":[],"attraction":["Activités concrètes"],
          "access":["Reste à vérifier"],"context":{"choices":["Je ne sais pas encore"],"other":""},"note":""})
    if not a["cav1"]["ideas"]: a["cav1"]["no_idea"] = True
    a["cav2"]["valeurs"]["choices"]=["Créativité","Respect"]
    a["cav2"]["moteurs"]["choices"]=["Innover","Comprendre"]
    a["cav2"]["preferences"]["priorities"]=[{"code":"PP2","pole":"EQUILIBRE","importance":"IMPORTANT_ADAPTABLE","other":"","note":""}]
    a["cav2"]["preferences"]["situation"]="NON"
    return a


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True,help="DB locale temporaire de recette, écrasée")
    p.add_argument("--signing-key",required=True,help="Clé temporaire fictive de recette")
    p.add_argument("--stage",choices=("draft","ready","answered","reviewed"),default="draft")
    p.add_argument("--scenario",choices=("two","zero","many"),default="two")
    args=p.parse_args()
    old=sys.argv
    try:
        sys.argv=["go21_demo_seed.py","--db",args.db,"--signing-key",args.signing_key]
        go21_demo_seed.main()
    finally:sys.argv=old
    url=f"sqlite:///{args.db}"
    eng=build_engine(url);Factory=session_factory(eng)
    acc=go21_demo_seed.context(ActorRole.ACCOMPAGNATEUR)
    ben=go21_demo_seed.context(ActorRole.BENEFICIAIRE)
    with Factory() as db:
        case=CaseRepository(db).open_or_create(acc)
        case_id=case.case_id
    v=create_questionnaire_v2(acc,case_id,synthetic_sources(args.scenario),context="AUTOFINANCE",
        intro="Simulation fictive GO22 : répondez librement, sans IA ni bonne réponse attendue.", database_url=url)
    if args.stage=="draft":
        print("GO22_RC3_STAGE=DRAFT: Accompagnateur prépare C-AV1 + C-AV2 puis verrouille Q.")
        return
    v=lock_questionnaire(acc,case_id,expected_row_version=v.row_version,database_url=url)
    v=open_beneficiary_access(acc,case_id,expected_row_version=v.row_version,database_url=url)
    if args.stage=="ready":
        print("GO22_RC3_STAGE=READY: Bénéficiaire répond à C-AV1 puis C-AV2.")
        return
    a=filled(v.questionnaire)
    a["cav1_done"]=True
    v=save_beneficiary_answers(ben,case_id,a,expected_row_version=v.row_version,database_url=url)
    a["cav2_done"]=True
    v=save_beneficiary_answers(ben,case_id,a,expected_row_version=v.row_version,database_url=url)
    v=submit_beneficiary_answers(ben,case_id,expected_row_version=v.row_version,database_url=url)
    if args.stage=="answered":
        print("GO22_RC3_STAGE=ANSWERED: R1 unique transmise, deux parties validées.")
        return
    r2=copy.deepcopy(a)
    r2["cav2"]["valeurs"]["choices"]=["Autonomie"]
    v=save_joint_review(acc,case_id,r2,expected_row_version=v.row_version,database_url=url)
    confirm_joint_review(acc,case_id,beneficiary_confirmed=True,method="PARTAGE_ECRAN_ORAL",expected_row_version=v.row_version,database_url=url)
    print("GO22_RC3_STAGE=REVIEWED: R1 historisée, R2 révalidée en partage d'écran.")


if __name__ == "__main__":main()
