from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from clarte360_cp.repositories import CaseRepository
from clarte360_cp.repositories.models import IntegrationImport, IntegrationOutbox
from .helpers import context


def case_id(Session):
    with Session() as s: return CaseRepository(s).open_or_create(context()).case_id


def test_outbox_idempotency_unique(Session):
    cid=case_id(Session)
    with Session() as s:
        row=dict(case_id=cid,event_type="RETURN",aggregate_type="ARTIFACT",aggregate_id="A1",payload_json_minimized="{}",idempotency_key="K1")
        s.add(IntegrationOutbox(**row)); s.commit()
    with Session() as s:
        s.add(IntegrationOutbox(**row))
        with pytest.raises(IntegrityError): s.commit()


def test_import_idempotency_unique(Session):
    cid=case_id(Session)
    row=dict(case_id=cid,source_system="GDA",source_ref="SRC-1",source_version="V1",sha256="a"*64,artifact_id="ART-1",idempotency_key="I1")
    with Session() as s: s.add(IntegrationImport(**row)); s.commit()
    with Session() as s:
        s.add(IntegrationImport(**row))
        with pytest.raises(IntegrityError): s.commit()
