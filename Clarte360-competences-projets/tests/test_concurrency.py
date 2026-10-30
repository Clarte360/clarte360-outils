from __future__ import annotations

import threading
from sqlalchemy.orm.exc import StaleDataError

from clarte360_cp.repositories import CaseRepository
from .helpers import context


def test_optimistic_lock_prevents_silent_overwrite(Session):
    with Session() as s:
        case=CaseRepository(s).open_or_create(context())
        cid=case.case_id
    s1, s2 = Session(), Session()
    try:
        a=s1.get(__import__('clarte360_cp.repositories.models',fromlist=['Case']).Case,cid)
        b=s2.get(__import__('clarte360_cp.repositories.models',fromlist=['Case']).Case,cid)
        a.current_phase=1; s1.commit()
        b.current_phase=2
        try:
            s2.commit(); ok=False
        except StaleDataError:
            s2.rollback(); ok=True
        assert ok
    finally:
        s1.close(); s2.close()


def test_distinct_cases_can_write_without_loss(Session):
    c1=context(prescription="P1",beneficiary="B1",action="A1",actor="U1")
    c2=context(prescription="P2",beneficiary="B2",action="A2",actor="U2")
    with Session() as s:
        a=CaseRepository(s).open_or_create(c1); id1=a.case_id
        b=CaseRepository(s).open_or_create(c2); id2=b.case_id
    errors=[]
    def worker(cid, phase):
        try:
            with Session() as s:
                x=CaseRepository(s).get(cid); v=x.row_version
                CaseRepository(s).advance_current_phase(cid,v,phase)
        except Exception as e: errors.append(e)
    t1=threading.Thread(target=worker,args=(id1,1)); t2=threading.Thread(target=worker,args=(id2,2))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert not errors
    with Session() as s:
        assert CaseRepository(s).get(id1).current_phase==1
        assert CaseRepository(s).get(id2).current_phase==2
