from sqlalchemy import text
from db import make_engine, init_db
from services import add_trainer


def _engine():
    e = make_engine('sqlite:///:memory:')
    init_db(e)
    return e


def test_j0_schema_and_stable_identity_for_new_trainer():
    e = _engine()
    tid = add_trainer(e, 'Jean Test', 'jean.test@example.org', '0102030405', 'admin')
    with e.connect() as c:
        tr = c.execute(text('SELECT * FROM trainers WHERE id=:i'), {'i': tid}).mappings().first()
        pp = c.execute(text('SELECT * FROM professional_persons WHERE trainer_id=:i'), {'i': tid}).mappings().first()
    assert tr['professional_person_id']
    assert pp['professional_person_id'] == tr['professional_person_id']
    assert pp['principal_status'] == 'INTERVENANT'
    assert pp['candidate_work_status'] == 'VALIDE'


def test_j0_init_is_idempotent_and_does_not_infer_qualification():
    e = _engine()
    tid = add_trainer(e, 'Marie Test', 'marie.test@example.org', None, 'admin')
    init_db(e)
    init_db(e)
    with e.connect() as c:
        n = c.execute(text('SELECT COUNT(*) FROM professional_persons WHERE trainer_id=:i'), {'i': tid}).scalar_one()
        tables = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert n == 1
    assert 'professional_persons' in tables
    assert 'professional_person_status_history' in tables
    # J0 is identity/status only; qualification tables arrive in later jalons.
    assert 'professional_qualifications' not in tables


def test_j0_historical_trainer_backfill_preserves_inactive_state():
    e = make_engine('sqlite:///:memory:')
    init_db(e)
    tid = add_trainer(e, 'Ancien Intervenant', 'ancien@example.org', None, 'admin')
    with e.begin() as c:
        c.execute(text('UPDATE trainers SET active=0 WHERE id=:i'), {'i': tid})
        c.execute(text('DELETE FROM professional_persons WHERE trainer_id=:i'), {'i': tid})
        c.execute(text('UPDATE trainers SET professional_person_id=NULL WHERE id=:i'), {'i': tid})
    init_db(e)
    with e.connect() as c:
        pp = c.execute(text('SELECT * FROM professional_persons WHERE trainer_id=:i'), {'i': tid}).mappings().first()
    assert pp['principal_status'] == 'INTERVENANT'
    assert pp['active'] == 0
