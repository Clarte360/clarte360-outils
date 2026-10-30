from __future__ import annotations

from clarte360_cp.domain.enums import ActorRole
from tools.go21_demo_seed import context


def test_go21_demo_tokens_are_bounded_to_security_window():
    for role in (ActorRole.ACCOMPAGNATEUR, ActorRole.BENEFICIAIRE):
        ctx = context(role)
        assert 0 < ctx.exp - ctx.iat <= 900


def test_go21_demo_uses_distinct_actor_ids_and_same_case_context():
    acc = context(ActorRole.ACCOMPAGNATEUR)
    ben = context(ActorRole.BENEFICIAIRE)
    assert acc.actor_id != ben.actor_id
    assert (acc.beneficiary_id, acc.action_id, acc.prescription_id) == (ben.beneficiary_id, ben.action_id, ben.prescription_id)
