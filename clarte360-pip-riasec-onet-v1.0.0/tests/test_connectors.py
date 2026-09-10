from pathlib import Path

import pytest

from clarte360_pip.connectors import GestionActionsPort, OnetPort, RomePort
from clarte360_pip.framework.config import load_onet_settings


def test_future_connectors_are_explicitly_inactive():
    with pytest.raises(NotImplementedError):
        GestionActionsPort().resolve_launch("x")
    with pytest.raises(NotImplementedError):
        OnetPort(load_onet_settings({})).fetch_interest_profiler()
    with pytest.raises(NotImplementedError):
        RomePort(Path("rome.xlsx")).explore_equivalent_profiles("RIA")
