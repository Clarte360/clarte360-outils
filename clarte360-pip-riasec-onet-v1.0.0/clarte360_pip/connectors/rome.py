from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RomePort:
    source_path: Path | None = None

    def explore_equivalent_profiles(self, riasec_profile: str):
        raise NotImplementedError("Exploration ROME volontairement non developpee en L1-A.")
