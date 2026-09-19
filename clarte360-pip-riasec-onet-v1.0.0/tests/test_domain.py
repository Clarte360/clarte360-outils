import pytest

from clarte360_pip.domain import LaunchContext, RunMode


def test_public_mode_refuses_clarte_identifiers():
    with pytest.raises(ValueError):
        LaunchContext(mode=RunMode.PUBLIC, action_id="A1").validate()


def test_public_mode_is_valid_without_identity():
    LaunchContext(mode=RunMode.PUBLIC).validate()


def test_accompaniment_requires_structuring_ids():
    with pytest.raises(ValueError):
        LaunchContext(mode=RunMode.ACCOMPANIMENT, beneficiary_id="B1").validate()


def test_accompaniment_context_valid():
    LaunchContext(
        mode=RunMode.ACCOMPANIMENT,
        beneficiary_id="B1",
        action_id="A1",
        prescription_id="P1",
        beneficiary_first_name="Alice",
        beneficiary_last_name="Martin",
        action_number="CLA0003",
        action_title="Bilan de compétences",
    ).validate()
