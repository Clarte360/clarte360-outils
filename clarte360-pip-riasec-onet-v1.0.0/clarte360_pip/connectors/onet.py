from __future__ import annotations

from dataclasses import dataclass

from clarte360_pip.framework.config import OnetSettings


@dataclass(frozen=True)
class OnetPort:
    settings: OnetSettings

    @property
    def available_for_future_increment(self) -> bool:
        return self.settings.configured

    def fetch_interest_profiler(self):
        raise NotImplementedError("Module O*NET volontairement non developpe en L1-A.")
