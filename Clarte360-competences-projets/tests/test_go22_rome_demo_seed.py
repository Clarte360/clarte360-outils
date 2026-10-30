from __future__ import annotations

import pytest

from clarte360_cp.application.intersession import read_intersession_tasks
from clarte360_cp.application.rome_matching import read_rome_matching_workspace
from clarte360_cp.connectors.gestion_actions import verify_launch_token
from clarte360_cp.domain.enums import ActorRole
from tests.helpers import KEY
from tools.go21_demo_seed import context
from tools.go22_rome_demo_seed import build_demo


def test_preview_seed_is_synthetic_and_contains_both_workflows(tmp_path):
    db_path = tmp_path / "rome-preview.sqlite3"
    result = build_demo(db_path, KEY)
    coach = context(ActorRole.ACCOMPAGNATEUR)
    beneficiary = context(ActorRole.BENEFICIAIRE)

    assert verify_launch_token(result["accompagnateur_token"], KEY).actor_role is ActorRole.ACCOMPAGNATEUR
    assert verify_launch_token(result["beneficiaire_token"], KEY).actor_role is ActorRole.BENEFICIAIRE
    workspace = read_rome_matching_workspace(coach, result["case_id"], database_url=f"sqlite:///{db_path}")
    assert workspace.targets[0].code == "M1203"
    assert len(workspace.targets[0].items) == 3
    assert {experience.kind for experience in workspace.experiences} == {"EMPLOI", "ETUDE", "FORMATION"}
    tasks = read_intersession_tasks(beneficiary, result["case_id"], database_url=f"sqlite:///{db_path}")
    assert tasks[0]["task_type"] == "OFFRES_EMPLOI"
    assert "fictives" in tasks[0]["goal"]

    with pytest.raises(FileExistsError):
        build_demo(db_path, KEY)
