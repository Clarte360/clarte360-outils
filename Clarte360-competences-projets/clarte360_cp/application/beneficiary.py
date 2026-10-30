from __future__ import annotations

from dataclasses import dataclass

from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.beneficiary import BeneficiaryRepository, BeneficiarySnapshot


@dataclass(frozen=True)
class BeneficiaryHomeView:
    snapshot: BeneficiarySnapshot
    to_read: int
    to_do: int
    to_validate: int
    done: int


def build_beneficiary_home(case_id: str, *, database_url: str | None = None) -> BeneficiaryHomeView:
    engine = build_engine(database_url)
    Factory = session_factory(engine)
    with Factory() as session:
        snapshot = BeneficiaryRepository(session).load(case_id)

    to_read = len(snapshot.published_documents) + int(snapshot.orientation_published_version is not None)
    to_do = sum(1 for task in snapshot.tasks if task.state in {"PUBLIEE", "EN_COURS"})
    to_validate = sum(1 for _phase, state in snapshot.phase_states if state == "EN_ATTENTE_BENEFICIAIRE")
    to_validate += int(snapshot.orientation_published_version is not None and snapshot.orientation_feedback is None)
    done = sum(1 for _phase, state in snapshot.phase_states if state in {"VALIDEE", "FIGEE_CLOTURE"})
    done += sum(1 for task in snapshot.tasks if task.state == "CLOTUREE")
    return BeneficiaryHomeView(snapshot, to_read, to_do, to_validate, done)
