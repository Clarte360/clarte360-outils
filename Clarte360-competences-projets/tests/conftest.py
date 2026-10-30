from __future__ import annotations

import pytest

from clarte360_cp.repositories import build_engine, init_database, session_factory


@pytest.fixture()
def engine(tmp_path):
    db = tmp_path / "cp.sqlite3"
    eng = build_engine(f"sqlite:///{db}")
    init_database(eng)
    return eng


@pytest.fixture()
def Session(engine):
    return session_factory(engine)
