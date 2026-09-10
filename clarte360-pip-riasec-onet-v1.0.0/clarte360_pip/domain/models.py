from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RunMode(str, Enum):
    PUBLIC = "PUBLIC"
    ACCOMPANIMENT = "ACCOMPAGNEMENT"


class Journey(str, Enum):
    PIP_ONLY = "PIP_SEUL"
    PIP_THEN_ONET = "PIP_PUIS_ONET60"


class RunStatus(str, Enum):
    CREATED = "CREE"
    STARTED = "EN_COURS"
    COMPLETED = "TERMINE"


@dataclass(frozen=True)
class LaunchContext:
    mode: RunMode
    beneficiary_id: str | None = None
    action_id: str | None = None
    participant_id: str | None = None
    prescription_id: str | None = None
    rights: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    def validate(self) -> None:
        if self.mode is RunMode.PUBLIC:
            forbidden = [self.beneficiary_id, self.action_id, self.participant_id, self.prescription_id]
            if any(forbidden):
                raise ValueError("Le mode PUBLIC ne peut porter aucun identifiant de dossier Clarte360.")
        elif not (self.beneficiary_id and self.action_id and self.prescription_id):
            raise ValueError(
                "Le mode ACCOMPAGNEMENT exige beneficiary_id, action_id et prescription_id."
            )


@dataclass
class PipRunState:
    external_session_id: str
    launch: LaunchContext
    status: RunStatus = RunStatus.CREATED
    journey: Journey = Journey.PIP_ONLY
    pip_answers: dict[str, int] = field(default_factory=dict)
    onet_answers: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
