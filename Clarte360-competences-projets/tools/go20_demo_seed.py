from __future__ import annotations

import argparse
import time
from pathlib import Path

from sqlalchemy import select

from clarte360_cp.connectors.gestion_actions import build_launch_token
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.domain.launch import ACCOMPAGNATEUR_SCOPES, LaunchContext
from clarte360_cp.repositories import CaseRepository, build_engine, init_database, session_factory
from clarte360_cp.repositories.models import Artifact, ArtifactVersion, IntersessionTask, PhaseState
from clarte360_cp.ui.spec import SOURCE_CARDS


BENEFICIARY = "BENEF_GO20_DEMO"
ACTION = "ACTION_GO20_DEMO"
PRESCRIPTION = "PRESC_GO20_DEMO"
PARTICIPANT = "PART_GO20_DEMO"
ACTOR = "ACTOR_GO20_DEMO"


def launch_context() -> LaunchContext:
    now = int(time.time())
    return LaunchContext(
        beneficiary_id=BENEFICIARY,
        action_id=ACTION,
        prescription_id=PRESCRIPTION,
        participant_id=PARTICIPANT,
        actor_role=ActorRole.ACCOMPAGNATEUR,
        actor_id=ACTOR,
        scopes=tuple(sorted(ACCOMPAGNATEUR_SCOPES)),
        token_version=1,
        iat=now,
        exp=now + 900,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Jeu synthétique GO20 pour recette visuelle temporaire.")
    parser.add_argument("--db", required=True, help="Chemin du fichier SQLite temporaire.")
    parser.add_argument("--signing-key", required=True, help="Clé HMAC fictive utilisée uniquement pour la recette.")
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    engine = build_engine(f"sqlite:///{db_path}")
    init_database(engine)
    Factory = session_factory(engine)
    ctx = launch_context()

    with Factory() as session:
        case = CaseRepository(session).open_or_create(ctx)
        case.current_phase = 0
        case.status = "ACTIF"
        phases = list(session.scalars(select(PhaseState).where(PhaseState.case_id == case.case_id)))
        for phase in phases:
            phase.state = "EN_COURS" if phase.phase_no == 0 else "DISPONIBLE"

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
                created_by=ACTOR,
            )
            session.add(version)
            session.flush()
            artifact.current_version_id = version.artifact_version_id

        session.add(IntersessionTask(
            case_id=case.case_id,
            task_type="ENQUETE_METIER",
            state="EN_COURS",
            question_or_goal="Vérifier les conditions d'exercice d'un métier cible.",
            created_by=ACTOR,
        ))
        session.commit()

    payload = {
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
        "actor_role": "ACCOMPAGNATEUR",
        "actor_id": ctx.actor_id,
        "scopes": list(ctx.scopes),
    }
    token = build_launch_token(payload, args.signing_key)
    print(token)


if __name__ == "__main__":
    main()
