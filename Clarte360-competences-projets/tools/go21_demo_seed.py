from __future__ import annotations

import argparse
import time
from pathlib import Path

from sqlalchemy import select

from clarte360_cp.connectors.gestion_actions import build_launch_token
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.domain.launch import ACCOMPAGNATEUR_SCOPES, BENEFICIAIRE_SCOPES, LaunchContext
from clarte360_cp.repositories import CaseRepository, build_engine, init_database, session_factory
from clarte360_cp.repositories.models import (
    Artifact,
    ArtifactVersion,
    CareerItem,
    ExplorationIdea,
    IntersessionTask,
    JobTarget,
    PhaseState,
    PublicationEvent,
)
from clarte360_cp.ui.spec import SOURCE_CARDS


BENEFICIARY = "BENEF_GO21_DEMO"
ACTION = "ACTION_GO21_DEMO"
PRESCRIPTION = "PRESC_GO21_DEMO"
PARTICIPANT = "PART_GO21_DEMO"
ACC_ACTOR = "ACTOR_ACC_GO21_DEMO"
BEN_ACTOR = "ACTOR_BEN_GO21_DEMO"


def context(role: ActorRole) -> LaunchContext:
    now = int(time.time())
    scopes = ACCOMPAGNATEUR_SCOPES if role is ActorRole.ACCOMPAGNATEUR else BENEFICIAIRE_SCOPES
    actor = ACC_ACTOR if role is ActorRole.ACCOMPAGNATEUR else BEN_ACTOR
    return LaunchContext(
        beneficiary_id=BENEFICIARY,
        action_id=ACTION,
        prescription_id=PRESCRIPTION,
        participant_id=PARTICIPANT,
        actor_role=role,
        actor_id=actor,
        scopes=tuple(sorted(scopes)),
        token_version=1,
        iat=now,
        exp=now + 900,
    )


def token(ctx: LaunchContext, signing_key: str) -> str:
    return build_launch_token({
        "v": 1,
        "iat": ctx.iat,
        "exp": ctx.exp,
        "beneficiary_id": ctx.beneficiary_id,
        "action_id": ctx.action_id,
        "prescription_id": ctx.prescription_id,
        "participant_id": ctx.participant_id,
        "tool_id": "COMPETENCES_PROJETS",
        "hub_source": "GESTION_ACTIONS",
        "scope_vocab": "CP_V1",
        "actor_role": ctx.actor_role.value,
        "actor_id": ctx.actor_id,
        "scopes": list(ctx.scopes),
    }, signing_key)


def main() -> None:
    parser = argparse.ArgumentParser(description="Jeu synthétique GO21 double interface + synchronisation.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--signing-key", required=True)
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    engine = build_engine(f"sqlite:///{db_path}")
    init_database(engine)
    Factory = session_factory(engine)
    acc = context(ActorRole.ACCOMPAGNATEUR)
    ben = context(ActorRole.BENEFICIAIRE)

    with Factory() as session:
        case = CaseRepository(session).open_or_create(acc)
        case.current_phase = 0
        case.status = "ACTIF"
        phases = list(session.scalars(select(PhaseState).where(PhaseState.case_id == case.case_id)))
        for phase in phases:
            if phase.phase_no == 0:
                phase.state = "EN_ATTENTE_BENEFICIAIRE"
            elif phase.phase_no == 1:
                phase.state = "DISPONIBLE"
            else:
                phase.state = "NON_DISPONIBLE"

        source_versions = {}
        for code, _label in SOURCE_CARDS:
            artifact = Artifact(
                case_id=case.case_id,
                artifact_type=code,
                artifact_class="SOURCE",
                owner_system="C&P" if code == "CV_SOURCE" else "GDA",
                visibility_default="INTERNE_ACCOMPAGNATEUR",
            )
            session.add(artifact)
            session.flush()
            version = ArtifactVersion(
                artifact_id=artifact.artifact_id,
                version_no=1,
                state="SOURCE",
                created_by=ACC_ACTOR,
            )
            session.add(version)
            session.flush()
            artifact.current_version_id = version.artifact_version_id
            source_versions[code] = (artifact, version)

        # Sortie propre de phase 0 : parcours professionnel enrichi, préparé en séance avec assistance IA.
        parcours_artifact = Artifact(
            case_id=case.case_id,
            artifact_type="PARCOURS_PRO_ENRICHI",
            artifact_class="LIVRABLE_BENEFICIAIRE",
            owner_system="C&P",
            visibility_default="BENEFICIAIRE_APRES_PUBLICATION",
        )
        session.add(parcours_artifact)
        session.flush()
        parcours_version = ArtifactVersion(
            artifact_id=parcours_artifact.artifact_id,
            version_no=1,
            state="PUBLIE_POUR_RELECTURE",
            created_by=ACC_ACTOR,
            content_json='{"label":"Parcours professionnel enrichi","assistance_ia":true}',
        )
        session.add(parcours_version)
        session.flush()
        parcours_artifact.current_version_id = parcours_version.artifact_version_id
        session.add(PublicationEvent(
            case_id=case.case_id,
            artifact_version_id=parcours_version.artifact_version_id,
            audience="BENEFICIAIRE",
            event_key="GO21-RC2-DEMO-PUBLISH-PARCOURS",
        ))

        # Deux sources explicitement publiées au bénéficiaire pour vérifier le cloisonnement.
        for code in ("BOUSSOLE_VALEURS", "PIP_REPORT"):
            artifact, version = source_versions[code]
            session.add(PublicationEvent(
                case_id=case.case_id,
                artifact_version_id=version.artifact_version_id,
                audience="BENEFICIAIRE",
                event_key=f"GO21-DEMO-PUBLISH-{code}",
            ))

        session.add_all([
            CareerItem(case_id=case.case_id, item_type="EMPLOI", title="Responsable QHSE", organization="Entreprise exemple", start_date="2021", end_date="2025"),
            CareerItem(case_id=case.case_id, item_type="FORMATION", title="Formation SST", organization="Organisme exemple", start_date="2024", end_date="2024"),
            CareerItem(case_id=case.case_id, item_type="LANGUE", title="Anglais — B2", organization=None),
        ])
        session.add_all([
            ExplorationIdea(case_id=case.case_id, wording_original="Responsable QHSE", wording_current="Responsable QHSE", origin="BENEFICIAIRE", created_by=ACC_ACTOR),
            ExplorationIdea(case_id=case.case_id, wording_original="Formateur prévention", wording_current="Formateur prévention", origin="DISCUSSION", created_by=ACC_ACTOR),
        ])
        session.add(JobTarget(case_id=case.case_id, rome_code="H1302", rome_label="Management et ingénierie Hygiène Sécurité Environnement", status="ACTIVE", selected_order=1))
        session.add(IntersessionTask(
            case_id=case.case_id,
            task_type="ENQUETE_METIER",
            state="PUBLIEE",
            question_or_goal="Vérifier les conditions réelles d'exercice du métier visé.",
            created_by=ACC_ACTOR,
        ))
        session.commit()

    print(f"ACCOMPAGNATEUR_TOKEN={token(acc, args.signing_key)}")
    print(f"BENEFICIAIRE_TOKEN={token(ben, args.signing_key)}")


if __name__ == "__main__":
    main()
