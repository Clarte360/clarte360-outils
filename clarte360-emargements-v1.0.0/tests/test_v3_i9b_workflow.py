from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from db import make_engine, init_db, one, q, execute
from services import (
    create_action, add_participant, add_slot, add_trainer, assign_trainer,
    set_attendance_status, create_beneficiary, beneficiary_for_participant,
    allowed_delivery_modes, normalize_delivery_mode, delivery_mode_label,
    slot_countersignature_eligibility, refresh_countersign_communications,
    validate_slot_offsets,
)
from excel_import import normalize_date_value


def eng():
    e=make_engine('sqlite:///:memory:');init_db(e);return e


def action(e,no='I9B-001',delivery='PRESENTIEL',expected=1):
    return create_action(e,{
        'action_no':no,'title':'I9-B','subtitle':None,'nature':'Formation','mode':'INTRA','delivery_mode':delivery,
        'client_name':None,'client_type':'Particulier','group_code':None,'planned_hours':1.5,'expected_participants':expected,
        'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,'location':'Paris','notes':None,'source':'TEST'
    },'test')


def test_i9b_modalities_are_controlled_by_prestation():
    assert allowed_delivery_modes('BILAN_COMPETENCES')==['PRESENTIEL','DISTANCIEL_VISIO','HYBRIDE']
    assert 'ELEARNING' in allowed_delivery_modes('FORMATION')
    assert normalize_delivery_mode('Distanciel-visioconférence','COACHING')=='DISTANCIEL_VISIO'
    assert delivery_mode_label('BLENDED')=='Blended learning'
    with pytest.raises(ValueError): normalize_delivery_mode('E-learning','COACHING')


def test_i9b_excel_serial_birth_date_31364_is_normalized():
    iso,src,converted=normalize_date_value(31364,field_name='Date de naissance')
    assert iso=='1985-11-13' and src=='31364' and converted
    assert normalize_date_value('13/11/1985')[0]=='1985-11-13'
    assert normalize_date_value('1985-11-13')[0]=='1985-11-13'
    with pytest.raises(ValueError): normalize_date_value('03/04/85',field_name='Date de naissance')


def test_i9b_exact_identity_is_linked_automatically_but_not_name_only():
    e=eng();aid=action(e)
    bid=create_beneficiary(e,'DUPONT','Anne','1990-01-01','anne@example.org',actor='test')
    pid,_=add_participant(e,aid,{'last_name':'Dupont','first_name':'Anne','birth_date':'1990-01-01','email':'a2@example.org'},'test')
    assert beneficiary_for_participant(e,pid)['id']==bid
    pid2,_=add_participant(e,aid,{'last_name':'Dupont','first_name':'Anne','birth_date':None,'email':'x@example.org'},'test')
    assert one(e,'SELECT beneficiary_id FROM participants WHERE id=:p',{'p':pid2})['beneficiary_id'] is None


def test_i9b_participant_added_after_activation_queues_planning_email():
    e=eng();aid=action(e,no='I9B-MAIL')
    execute(e,"UPDATE actions SET status='ACTIVE' WHERE id=:a",{'a':aid})
    pid,_=add_participant(e,aid,{'last_name':'MARTIN','first_name':'Paul','birth_date':'1991-01-01','email':'paul@example.org'},'test')
    ev=one(e,"SELECT * FROM communication_events WHERE action_id=:a AND participant_id=:p AND communication_type='PLANNING_CONFIRMATION'",{'a':aid,'p':pid})
    assert ev and ev['status']=='A_ENVOYER' and ev['trigger_mode']=='AUTO'


def test_i9b_countersign_request_immediate_if_all_final_otherwise_at_end():
    e=eng();aid=action(e,no='I9B-CS',expected=1)
    t=add_trainer(e,'Coach Test','coach@example.org','','test');assign_trainer(e,aid,t,'test')
    p,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'a@example.org'},'test')
    sid=add_slot(e,aid,'2026-09-20','09:00','10:30','test')
    execute(e,"UPDATE actions SET status='ACTIVE' WHERE id=:a",{'a':aid})
    now=datetime(2026,9,12,10,0,tzinfo=ZoneInfo('UTC'))
    refresh_countersign_communications(e,now=now)
    ev=one(e,"SELECT * FROM communication_events WHERE communication_type='COUNTERSIGN_REQUEST' AND slot_id=:s",{'s':sid})
    assert ev and ev['due_at'].startswith('2026-09-20T')
    set_attendance_status(e,p,sid,'ABSENT','test','test')
    assert slot_countersignature_eligibility(e,sid,t,now=datetime(2026,9,12,12,0,tzinfo=ZoneInfo('Europe/Paris')))[0]
    refresh_countersign_communications(e,now=now)
    ev2=one(e,"SELECT * FROM communication_events WHERE id=:i",{'i':ev['id']})
    assert ev2['due_at'].startswith('2026-09-12T10:00:00')


def test_i9b_slot_offset_bounds_accept_minus_10_and_reject_absurd_values():
    assert validate_slot_offsets(-10,1440)==(-10,1440)
    with pytest.raises(ValueError): validate_slot_offsets(-1441,1440)
    with pytest.raises(ValueError): validate_slot_offsets(-10,10081)

def test_i9b_worker_sends_generic_planning_communication(monkeypatch):
    import worker
    from services import queue_communication
    e=eng();aid=action(e,no='I9B-WORKER')
    pid,_=add_participant(e,aid,{'last_name':'TEST','first_name':'Mail','birth_date':'1992-01-01','email':'mail@example.org'},'test')
    add_slot(e,aid,'2026-09-15','09:00','10:30','test')
    eid=queue_communication(e,aid,'PLANNING_CONFIRMATION','mail@example.org',participant_id=pid,due_at='2000-01-01T00:00:00+00:00')
    sent=[]
    monkeypatch.setattr(worker,'send_mail',lambda cfg,to,subject,body: sent.append((to,subject,body)))
    n=worker._run_communication_events(e,{'enabled':True,'from_email':'x@example.org'},'https://example.org')
    assert n==1 and sent and sent[0][0]=='mail@example.org'
    assert one(e,'SELECT status FROM communication_events WHERE id=:i',{'i':eid})['status']=='ENVOYE'
