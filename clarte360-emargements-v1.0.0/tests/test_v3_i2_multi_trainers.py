from db import make_engine, init_db, q, one
from services import (
    create_action, add_slot, add_trainer, assign_trainer,
    assign_action_trainer, assign_slot_trainer, replace_slot_trainer,
    list_action_trainers, list_slot_trainers, trainer_actions,
    trainer_action_dashboard, report_slot, create_catchup_slot,
)


def _action(e,no):
    return create_action(e,{
        'action_no':no,'title':'Action I2','subtitle':None,'nature':'FORMATION','mode':'PRESENTIEL',
        'client_name':'Client','client_type':'Entreprise','group_code':None,'planned_hours':7,
        'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Paris','notes':None,'source':'TEST'
    },'test')


def test_i2_multiple_action_and_slot_trainers_with_restricted_slot_visibility():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=_action(e,'V3I2001')
    t1=add_trainer(e,'Référent','ref@example.org','','test')
    t2=add_trainer(e,'Co intervenant','co@example.org','','test')
    assign_trainer(e,aid,t1,'test')
    s1=add_slot(e,aid,'2026-09-20','09:00','12:00','test')
    s2=add_slot(e,aid,'2026-09-21','09:00','12:00','test')
    ok,_=assign_action_trainer(e,aid,t2,'test',role='INTERVENANT',is_referent=False); assert ok
    ok,_=assign_slot_trainer(e,s2,t2,'test',role='CO_INTERVENANT'); assert ok
    assert len(list_action_trainers(e,aid))==2
    assert {x['trainer_id'] for x in list_slot_trainers(e,s2)}=={t1,t2}
    assert aid in {x['id'] for x in trainer_actions(e,t2)}
    dash=trainer_action_dashboard(e,t2,aid)
    assert dash is not None
    assert [x['id'] for x in dash['slots']]==[s2]
    assert [x['id'] for x in trainer_action_dashboard(e,t1,aid)['slots']]==[s1,s2]


def test_i2_replacement_preserves_original_assignment_and_history():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=_action(e,'V3I2002')
    t1=add_trainer(e,'Initial','initial@example.org','','test')
    t2=add_trainer(e,'Remplaçant','replacement@example.org','','test')
    assign_trainer(e,aid,t1,'test'); sid=add_slot(e,aid,'2026-09-22','13:00','17:00','test')
    old=one(e,'SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t',{'s':sid,'t':t1})
    ok,msg=replace_slot_trainer(e,sid,t1,t2,'test','Indisponibilité'); assert ok,msg
    old2=one(e,'SELECT * FROM slot_trainers WHERE id=:i',{'i':old['id']})
    new=one(e,'SELECT * FROM slot_trainers WHERE slot_id=:s AND trainer_id=:t',{'s':sid,'t':t2})
    assert old2['active']==0 and old2['assignment_status']=='REPLACED'
    assert new['active']==1 and new['role']=='REMPLACANT' and new['replaced_assignment_id']==old['id']
    events=[x['event_type'] for x in q(e,'SELECT event_type FROM trainer_assignment_history WHERE slot_id=:s ORDER BY id',{'s':sid})]
    assert 'UNASSIGNED' in events and 'ASSIGNED' in events


def test_i2_report_and_catchup_copy_real_slot_assignments():
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=_action(e,'V3I2003')
    t1=add_trainer(e,'Principal','principal@example.org','','test')
    t2=add_trainer(e,'Co animation','coanim@example.org','','test')
    assign_trainer(e,aid,t1,'test'); sid=add_slot(e,aid,'2026-09-23','09:00','12:00','test')
    assign_slot_trainer(e,sid,t2,'test','CO_INTERVENANT')
    ns=report_slot(e,sid,'2026-09-24','10:00','13:00','test','Décalage client')
    copied={(x['trainer_id'],x['role']) for x in list_slot_trainers(e,ns)}
    assert copied=={(t1,'PRINCIPAL'),(t2,'CO_INTERVENANT')}
    cs=create_catchup_slot(e,ns,'2026-09-25','14:00','15:00',[],'test','Rattrapage')
    copied2={(x['trainer_id'],x['role']) for x in list_slot_trainers(e,cs)}
    assert copied2==copied
