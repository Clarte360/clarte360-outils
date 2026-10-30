from __future__ import annotations

import time

from clarte360_cp.connectors.gestion_actions import build_launch_token, verify_launch_token

KEY = "k" * 40


def payload(role="ACCOMPAGNATEUR", scopes=None, *, beneficiary="BEN-1", action="ACT-1", prescription="PRE-1", actor="USR-1"):
    now = int(time.time())
    if scopes is None:
        scopes = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_VALIDATE"] if role == "ACCOMPAGNATEUR" else ["CP_CASE_OPEN", "CP_CASE_READ"]
    return {
        "v": 1,
        "iat": now,
        "exp": now + 600,
        "beneficiary_id": beneficiary,
        "action_id": action,
        "prescription_id": prescription,
        "tool_id": "COMPETENCES_PROJETS",
        "hub_source": "GESTION_ACTIONS",
        "scope_vocab": "CP_V1",
        "actor_role": role,
        "actor_id": actor,
        "scopes": scopes,
    }


def context(**kwargs):
    p = payload(**kwargs)
    return verify_launch_token(build_launch_token(p, KEY), KEY, now_epoch=p["iat"])
