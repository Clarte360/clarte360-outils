from db import make_engine, init_db, q, one, execute, utcnow_iso
from services import create_action, add_slot, add_trainer, assign_trainer, safe_set_action_modules


def _action(e, no='V3I1001', mode='INTRA'):
    return create_action(e, {
        'action_no':no, 'title':'Action I1', 'subtitle':None, 'nature':'Formation', 'mode':mode,
        'client_name':'Client', 'client_type':'Entreprise', 'group_code':None, 'planned_hours':7,
        'expected_participants':1, 'admin_email':'admin@example.org', 'trainer_name':None,
        'trainer_email':None, 'location':'Paris', 'notes':None, 'source':'TEST'
    }, 'test')


def test_i1_schema_is_additive_and_present():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    names={r['name'] for r in q(e,"SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'action_trainers','slot_trainers','trainer_assignment_history','action_modules'} <= names
    # V2 compatibility columns still exist.
    cols={r['name'] for r in q(e,"PRAGMA table_info(actions)")}
    assert {'trainer_id','use_attendance','use_quality_hot','use_quality_cold','use_trainer_feedback'} <= cols


def test_i1_v2_backfill_creates_referent_slot_assignment_and_history():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=_action(e,'V3I1002')
    tid=add_trainer(e,'Ancien formateur','old@example.org','','test')
    # Simulate V2 rows, then remove only the V3 I1 structures before re-running init_db.
    execute(e,"UPDATE actions SET trainer_id=:t,trainer_name='Ancien formateur',trainer_email='old@example.org' WHERE id=:a",{'t':tid,'a':aid})
    now=utcnow_iso()
    sid=execute(e,"""INSERT INTO slots(action_id,slot_date,start_time,end_time,original_start_time,original_end_time,public_token,created_at,updated_at)
        VALUES(:a,'2026-09-10','09:00','12:00','09:00','12:00','raw-v2',:n,:n)""",{'a':aid,'n':now})
    with e.begin() as c:
        c.exec_driver_sql('DROP TABLE trainer_assignment_history')
        c.exec_driver_sql('DROP TABLE slot_trainers')
        c.exec_driver_sql('DROP TABLE action_trainers')
        c.exec_driver_sql('DROP TABLE action_modules')
    init_db(e)
    at=one(e,'SELECT * FROM action_trainers WHERE action_id=:a AND trainer_id=:t',{'a':aid,'t':tid})
    st=one(e,'SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t',{'s':sid,'t':tid})
    assert at and at['role']=='REFERENT' and at['is_referent']==1 and at['active']==1
    assert st and st['role']=='PRINCIPAL' and st['assignment_status']=='ACTIVE' and st['active']==1
    assert one(e,"SELECT id FROM trainer_assignment_history WHERE migration_key=:k",{'k':f'V2_ACTION_{aid}_{tid}'})
    assert one(e,"SELECT id FROM trainer_assignment_history WHERE migration_key=:k",{'k':f'V2_SLOT_{sid}_{tid}'})


def test_i1_backfill_is_idempotent():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=_action(e,'V3I1003'); tid=add_trainer(e,'Référent','ref@example.org','','test')
    assign_trainer(e,aid,tid,'test'); add_slot(e,aid,'2026-09-11','09:00','12:00','test')
    init_db(e)
    counts1={
        'at':one(e,'SELECT COUNT(*) n FROM action_trainers')['n'],
        'st':one(e,'SELECT COUNT(*) n FROM slot_trainers')['n'],
        'hist':one(e,'SELECT COUNT(*) n FROM trainer_assignment_history')['n'],
        'mods':one(e,'SELECT COUNT(*) n FROM action_modules')['n'],
    }
    init_db(e)
    counts2={
        'at':one(e,'SELECT COUNT(*) n FROM action_trainers')['n'],
        'st':one(e,'SELECT COUNT(*) n FROM slot_trainers')['n'],
        'hist':one(e,'SELECT COUNT(*) n FROM trainer_assignment_history')['n'],
        'mods':one(e,'SELECT COUNT(*) n FROM action_modules')['n'],
    }
    assert counts1==counts2


def test_i1_assign_trainer_keeps_v2_and_v3_in_sync():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=_action(e,'V3I1004'); sid=add_slot(e,aid,'2026-09-12','09:00','12:00','test')
    t1=add_trainer(e,'Premier','first@example.org','','test')
    t2=add_trainer(e,'Second','second@example.org','','test')
    assign_trainer(e,aid,t1,'test')
    assert one(e,'SELECT trainer_id FROM actions WHERE id=:a',{'a':aid})['trainer_id']==t1
    assert one(e,'SELECT active FROM action_trainers WHERE action_id=:a AND trainer_id=:t',{'a':aid,'t':t1})['active']==1
    assert one(e,'SELECT active FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t',{'s':sid,'t':t1})['active']==1
    assign_trainer(e,aid,t2,'test')
    assert one(e,'SELECT trainer_id FROM actions WHERE id=:a',{'a':aid})['trainer_id']==t2
    assert one(e,'SELECT active FROM action_trainers WHERE action_id=:a AND trainer_id=:t',{'a':aid,'t':t1})['active']==0
    assert one(e,'SELECT active FROM action_trainers WHERE action_id=:a AND trainer_id=:t',{'a':aid,'t':t2})['active']==1
    assert one(e,'SELECT assignment_status FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t',{'s':sid,'t':t1})['assignment_status']=='REPLACED'
    assert one(e,'SELECT active FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t',{'s':sid,'t':t2})['active']==1


def test_i1_new_slot_inherits_current_referent_for_v2_compatibility():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=_action(e,'V3I1005'); tid=add_trainer(e,'Référent','referent@example.org','','test')
    assign_trainer(e,aid,tid,'test')
    sid=add_slot(e,aid,'2026-09-13','13:00','17:00','test')
    row=one(e,'SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t',{'s':sid,'t':tid})
    assert row and row['role']=='PRINCIPAL' and row['active']==1


def test_i1_action_modules_mirror_v2_and_teams_never_auto_activates():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=_action(e,'V3I1006','DISTANCIEL')
    safe_set_action_modules(e,aid,'FORMATION',True,True,False,True,None,'','test')
    mods={r['module_code']:r['enabled'] for r in q(e,'SELECT module_code,enabled FROM action_modules WHERE action_id=:a',{'a':aid})}
    assert mods['ATTENDANCE']==1
    assert mods['QUALITY_HOT']==1
    assert mods['QUALITY_COLD']==0
    assert mods['TRAINER_FEEDBACK']==1
    assert mods['TEAMS']==0
    assert mods['BENEFICIARY_PORTAL']==0
    assert mods['COURSE_DOCUMENTS']==0
    assert mods['CLIENT_TRANSMISSION']==0


def test_i1_unassign_deactivates_v3_assignments_without_deleting_history():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=_action(e,'V3I1007'); tid=add_trainer(e,'Référent','unassign@example.org','','test')
    assign_trainer(e,aid,tid,'test'); sid=add_slot(e,aid,'2026-09-14','09:00','10:00','test')
    before=one(e,'SELECT COUNT(*) n FROM trainer_assignment_history WHERE action_id=:a',{'a':aid})['n']
    assign_trainer(e,aid,'','test')
    assert one(e,'SELECT trainer_id FROM actions WHERE id=:a',{'a':aid})['trainer_id'] is None
    assert one(e,'SELECT active FROM action_trainers WHERE action_id=:a AND trainer_id=:t',{'a':aid,'t':tid})['active']==0
    assert one(e,'SELECT active FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t',{'s':sid,'t':tid})['active']==0
    after=one(e,'SELECT COUNT(*) n FROM trainer_assignment_history WHERE action_id=:a',{'a':aid})['n']
    assert after > before
