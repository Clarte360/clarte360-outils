from __future__ import annotations

from dataclasses import dataclass

from clarte360_pip.domain import LaunchContext


@dataclass(frozen=True)
class GestionActionsPort:
    """L1-A contract boundary only. No V3 integration is implemented in this increment."""

    enabled: bool = False

    def resolve_launch(self, token: str) -> LaunchContext:
        raise NotImplementedError("Connecteur Gestion des actions prevu dans un lot ulterieur.")

    def publish_event(self, event_type: str, payload: dict) -> None:
        raise NotImplementedError("Publication d'evenements prevue dans un lot ulterieur.")
