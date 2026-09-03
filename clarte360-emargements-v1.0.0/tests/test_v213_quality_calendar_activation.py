from pathlib import Path

from db import make_engine, init_db, one, execute
from services import (
    create_action, add_participant, add_slot, activate_action,
    ensure_default_organization, safe_set_action_modules,
    prepare_quality_campaigns, standard_quality_due,
    reschedule_pending_quality_campaigns, local_dt,
)


def eng():
    e=make_engine('sqlite:///:memory:')
    init_db(e)
    ensure_default_organization(e)
    return e


def base_action(e, no='T213', planned=1.5):
    aid=create_action(e,{
        'action_no':no,'title':'Test V2.1.3','subtitle':None,'nature':'Formation','mode':'INDIVIDUEL',
        'client_name':None,'client_type':'Non précisé','group_code':None,'planned_hours':planned,
        'expected_participants':1,'admin_email':'a@b.fr','trainer_name':None,'trainer_email':None,
        'location':'Teams','notes':None,'source':'TEST'
    },'test')
    execute(e,"UPDATE actions SET start_date='2026-09-01',end_date='2026-12-31' WHERE id=:a",{'a':aid})
    return aid


def test_quality_uses_real_last_session_not_administrative_end_date():
    e=eng(); aid=base_action(e,planned=3)
    add_slot(e,aid,'2026-09-04','11:00','12:30','test',send=-90)
    add_slot(e,aid,'2026-11-19','19:00','20:30','test',send=-90)
    hot=local_dt(standard_quality_due(e,aid,'HOT'),'Europe/Paris')
    cold=local_dt(standard_quality_due(e,aid,'COLD'),'Europe/Paris')
    assert hot.strftime('%Y-%m-%d %H:%M')=='2026-11-19 20:30'
    assert cold.strftime('%Y-%m-%d %H:%M')=='2027-02-17 12:00'


def test_quality_handles_overnight_last_session():
    e=eng(); aid=base_action(e,planned=1)
    add_slot(e,aid,'2026-09-03','23:00','00:00','test',send=-60)
    hot=local_dt(standard_quality_due(e,aid,'HOT'),'Europe/Paris')
    assert hot.strftime('%Y-%m-%d %H:%M')=='2026-09-04 00:00'


def test_pending_quality_campaigns_follow_calendar_change():
    e=eng(); aid=base_action(e,planned=1.5)
    org=one(e,'SELECT id FROM organizations ORDER BY id LIMIT 1')
    safe_set_action_modules(e,aid,'FORMATION',True,True,True,False,org['id'],None,'test')
    add_participant(e,aid,{'last_name':'DURAND','first_name':'Marie','email':'m@example.fr'},'test')
    sid=add_slot(e,aid,'2026-11-19','19:00','20:30','test',send=-90)
    made=prepare_quality_campaigns(e,aid,'https://example.fr','test')
    assert len(made)==2
    before=one(e,"SELECT due_at FROM quality_campaigns WHERE action_id=:a AND campaign_kind='HOT'",{'a':aid})['due_at']
    execute(e,"UPDATE slots SET slot_date='2026-11-20' WHERE id=:s",{'s':sid})
    changed=reschedule_pending_quality_campaigns(e,aid,'test')
    after=one(e,"SELECT due_at FROM quality_campaigns WHERE action_id=:a AND campaign_kind='HOT'",{'a':aid})['due_at']
    ev=one(e,"SELECT qe.due_at FROM quality_email_events qe JOIN quality_campaigns c ON c.id=qe.campaign_id WHERE c.action_id=:a AND c.campaign_kind='HOT' AND qe.event_type='INITIAL'",{'a':aid})['due_at']
    assert changed>=1
    assert before!=after
    assert local_dt(after,'Europe/Paris').strftime('%Y-%m-%d')=='2026-11-20'
    assert ev==after


def test_activation_rejects_incoherent_attendance_calendar():
    e=eng(); aid=base_action(e,planned=3)
    add_participant(e,aid,{'last_name':'DURAND','first_name':'Marie','email':'m@example.fr'},'test')
    add_slot(e,aid,'2026-09-04','09:00','10:30','test',send=-90)
    ok,issues=activate_action(e,aid,'test')
    assert not ok
    assert any('Calendrier incohérent' in x for x in issues)


def test_app_exposes_activation_in_calendar_and_dispatch_without_magic_delta_expression():
    text=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
    assert "activate_action_ui(a,'calendar')" in text
    assert "activate_action_ui(a,'dispatch')" in text
    assert "(st.success(msgm) if okm else st.warning(msgm))" not in text
