from pathlib import Path

import pytest

from clarte360_pip.connectors import GestionActionsPort, OnetPort, RomePort
from clarte360_pip.connectors.gestion_actions import LaunchTokenError
from clarte360_pip.framework.config import load_onet_settings


def test_gestion_actions_connector_requires_vps_signing_secret():
    with pytest.raises(LaunchTokenError):
        GestionActionsPort().resolve_launch("x")
    from clarte360_pip.connectors.onet import OnetApiError
    with pytest.raises(OnetApiError):
        OnetPort(load_onet_settings({})).fetch_interest_profiler()
    with pytest.raises(NotImplementedError):
        RomePort(Path("rome.xlsx")).explore_equivalent_profiles("RIA")
