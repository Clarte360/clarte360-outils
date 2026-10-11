"""J11 / P5-RC2: durable, user-controlled reminders for online Teams sessions.

Fictitious SQLite and SMTP only. Never connects to Graph, VPS, or real mail.
"""
from datetime import datetime as RealDateTime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import json

import pytest
from sqlalchemy import inspect

import worker
from db import make_engine, init_db, one, q, execute, utcnow_iso
from regional_settings import (REMINDER_DEFAULTS, online_reminders_from_org,
    validate_online_reminders, format_online_reminder_delay)
from services import (ensure_default_organization, get_organization, create_action,
    add_participant, add_slot, report_slot, save_regional_preferences,
    get_online_reminder_preferences, online_reminder_offsets_for_action,
    synchronize_teams_reminders, teams_reminder_event_state, refresh_all_worker_events)

START = RealDateTime(2030, 6, 10, 12, 0, tzinfo=ZoneInfo('Europe/Paris'))
START_UTC = START.astimezone(timezone.utc)


def setup(tmp_path, suffix='a'):
    engine=make_engine('sqlite:///'+str(tmp_path/f'online_reminders_{suffix}.db'))
    init_db(engine); oid=ensure_default_organization(engine)
    action=create_action(engine,dict(action_no=f'ONLINE-{suffix}',title='Séance en ligne fictive',
        subtitle=None,nature='FORMATION',mode='DISTANCIEL',client_name='Entreprise fictive',
        client_type='Entreprise',group_code=None,planned_hours=1,expected_participants=1,
        admin_email='admin@example.invalid',trainer_name=None,trainer_email=None,
        location='En ligne',notes=None,source='J11_TEST'),'j11-test')
    execute(engine,"UPDATE actions SET status='ACTIVE',organization_id=:o WHERE id=:a",{'o':oid,'a':action})
    execute(engine,"""INSERT INTO action_modules(action_id,module_code,enabled,enabled_at,enabled_by,created_at,updated_at)
        VALUES(:a,'TEAMS',1,:t,'test',:t,:t)""",{'a':action,'t':utcnow_iso()})
    pid,_=add_participant(engine,action,{'last_name':'FICTIF','first_name':'Participant',
        'birth_date':'1990-01-01','email':'person@example.invalid'},'test')
    slot=add_slot(engine,action,START.date().isoformat(),START.strftime('%H:%M'),
        (START+timedelta(hours=1)).strftime('%H:%M'),'test')
    # Focus the SMTP-simulated tests on reminders; preserve the unrelated
    # automatic planning confirmation as an already handled historical event.
    execute(engine,"UPDATE communication_events SET status='ANNULE' WHERE communication_type='PLANNING_CONFIRMATION'")
    return engine,oid,action,pid,slot


def save(engine,oid,first,second,*,tz='Europe/Paris'):
    return save_regional_preferences(engine,oid,timezone_name=tz,date_format='FR',
        time_format='24H',language='fr',actor='test-admin',first_reminder_minutes=first,
        second_reminder_minutes=second)


def rows(engine,sid):
    return q(engine,"""SELECT * FROM communication_events WHERE slot_id=:s AND
        communication_type IN ('TEAMS_REMINDER_H2','TEAMS_REMINDER_H15') ORDER BY id""",{'s':sid})


def clock_worker(monkeypatch,when):
    class FixedDateTime(RealDateTime):
        @classmethod
        def now(cls,tz=None):
            return when.astimezone(tz) if tz else when.replace(tzinfo=None)
    monkeypatch.setattr(worker,'datetime',FixedDateTime)


def test_default_two_delays_and_history_codes_unchanged(tmp_path):
    e,oid,aid,pid,sid=setup(tmp_path)
    assert get_online_reminder_preferences(e)==REMINDER_DEFAULTS
    assert get_online_reminder_preferences(e,aid)==REMINDER_DEFAULTS
    assert set(online_reminder_offsets_for_action(e,aid))=={'TEAMS_REMINDER_H2','TEAMS_REMINDER_H15'}
    pending={r['communication_type']:r for r in rows(e,sid)}
    assert pending['TEAMS_REMINDER_H2']['due_at']==(START_UTC-timedelta(minutes=120)).isoformat()
    assert pending['TEAMS_REMINDER_H15']['due_at']==(START_UTC-timedelta(minutes=15)).isoformat()
    assert format_online_reminder_delay(120)=='2 heures'
    assert format_online_reminder_delay(15)=='15 minutes'
    assert format_online_reminder_delay(1)=='1 minute'
    assert format_online_reminder_delay(75)=='1 h 15'


@pytest.mark.parametrize('a,b',[(0,2),(-1,2),(10081,15),(2,2),(1,2),(2.5,1),
                                  ('text',1),(True,1),(None,1),(' 5',2)])
def test_invalid_values_refused(a,b):
    with pytest.raises(ValueError): validate_online_reminders(a,b)


def test_invalid_form_does_not_save_any_regional_or_reminder_changes(tmp_path):
    e,oid,aid,pid,sid=setup(tmp_path)
    before=one(e,'SELECT timezone,online_reminder_first_minutes,online_reminder_second_minutes FROM organizations WHERE id=:o',{'o':oid})
    with pytest.raises(ValueError): save(e,oid,2,5,tz='Europe/Budapest')
    after=one(e,'SELECT timezone,online_reminder_first_minutes,online_reminder_second_minutes FROM organizations WHERE id=:o',{'o':oid})
    assert before==after
    assert all(r['status']=='A_ENVOYER' for r in rows(e,sid))


def test_admin_can_choose_5_and_2_then_restore_120_and_15_manually(tmp_path):
    e,oid,aid,pid,sid=setup(tmp_path)
    original=rows(e,sid)
    assert len(original)==2
    save(e,oid,5,2)
    after=rows(e,sid)
    assert get_online_reminder_preferences(e,aid)=={'online_reminder_first_minutes':5,'online_reminder_second_minutes':2}
    assert all(one(e,'SELECT status FROM communication_events WHERE id=:i',{'i':r['id']})['status']=='ANNULE' for r in original)
    assert {r['communication_type']:r['due_at'] for r in after if r['status']=='A_ENVOYER'}=={
        'TEAMS_REMINDER_H2':(START_UTC-timedelta(minutes=5)).isoformat(),
        'TEAMS_REMINDER_H15':(START_UTC-timedelta(minutes=2)).isoformat()}
    init_db(e);init_db(e)
    assert get_online_reminder_preferences(e,aid)['online_reminder_first_minutes']==5
    # There is intentionally no automatic reset, even across restarts.
    save_regional_preferences(e,oid,timezone_name='Europe/Paris',date_format='US',time_format='12H',language='en',actor='test-admin')
    assert get_online_reminder_preferences(e,aid)['online_reminder_second_minutes']==2
    save(e,oid,120,15)
    assert {r['communication_type']:r['due_at'] for r in rows(e,sid) if r['status']=='A_ENVOYER'}=={
        'TEAMS_REMINDER_H2':(START_UTC-timedelta(minutes=120)).isoformat(),
        'TEAMS_REMINDER_H15':(START_UTC-timedelta(minutes=15)).isoformat()}
    assert len([r for r in rows(e,sid) if r['status']=='A_ENVOYER'])==2


def test_test_timing_correct_subject_and_body_and_no_duplicates(tmp_path,monkeypatch):
    e,oid,aid,pid,sid=setup(tmp_path)
    save(e,oid,5,2)
    sends=[]
    monkeypatch.setattr(worker,'send_mail',lambda cfg,to,subj,html:sends.append((to,subj,html)))
    clock_worker(monkeypatch,START_UTC-timedelta(minutes=5))
    assert worker._run_communication_events(e,{},'https://example.invalid')==1
    assert 'dans 5 minutes' in sends[0][1]
    assert 'dans <strong>5 minutes</strong>' in sends[0][2]
    clock_worker(monkeypatch,START_UTC-timedelta(minutes=2))
    assert worker._run_communication_events(e,{},'https://example.invalid')==1
    assert 'dans 2 minutes' in sends[1][1]
    assert 'dans <strong>2 minutes</strong>' in sends[1][2]
    for _ in range(3):
        synchronize_teams_reminders(e,now=START_UTC-timedelta(minutes=2))
        assert worker._run_communication_events(e,{},'https://example.invalid')==0
    assert len(sends)==2


def test_setting_change_cancels_old_pending_and_revalidation_at_send_time(tmp_path,monkeypatch):
    e,oid,aid,pid,sid=setup(tmp_path)
    old=next(r for r in rows(e,sid) if r['communication_type']=='TEAMS_REMINDER_H2')
    save(e,oid,5,2)
    assert one(e,'SELECT status FROM communication_events WHERE id=:id',{'id':old['id']})['status']=='ANNULE'
    # Even an accidentally reactivated legacy row is rejected before SMTP.
    execute(e,"UPDATE communication_events SET status='A_ENVOYER',due_at=:d WHERE id=:i",
        {'d':(START_UTC-timedelta(minutes=120)).isoformat(),'i':old['id']})
    clock_worker(monkeypatch,START_UTC-timedelta(minutes=5))
    sent=[];monkeypatch.setattr(worker,'send_mail',lambda *args:sent.append(args))
    worker._run_communication_events(e,{},'https://example.invalid')
    assert len(sent)==1  # correct 5-minute reminder, never the obsolete H-2 row
    assert one(e,'SELECT status FROM communication_events WHERE id=:i',{'i':old['id']})['status']=='ANNULE'


def test_already_sent_is_not_repeated_after_a_settings_change(tmp_path,monkeypatch):
    e,oid,aid,pid,sid=setup(tmp_path)
    save(e,oid,5,2)
    clock_worker(monkeypatch,START_UTC-timedelta(minutes=5))
    sent=[];monkeypatch.setattr(worker,'send_mail',lambda cfg,to,subj,html:sent.append(subj))
    assert worker._run_communication_events(e,{},'https://example.invalid')==1
    save(e,oid,6,2)
    assert not [r for r in rows(e,sid) if r['status']=='A_ENVOYER' and r['communication_type']=='TEAMS_REMINDER_H2']
    assert worker._run_communication_events(e,{},'https://example.invalid')==0
    assert len(sent)==1


def test_five_minute_reminder_does_not_claim_two_minutes_late(tmp_path):
    e,oid,aid,pid,sid=setup(tmp_path)
    save(e,oid,5,2)
    first=next(r for r in rows(e,sid) if r['status']=='A_ENVOYER' and r['communication_type']=='TEAMS_REMINDER_H2')
    ok,reason,_=teams_reminder_event_state(e,first,now=START_UTC-timedelta(minutes=3),enforce_due=True)
    assert not ok and reason=='REMINDER_EXPIRED'


def test_first_reminder_is_invalid_once_second_window_begins(tmp_path):
    e,oid,aid,pid,sid=setup(tmp_path)
    save(e,oid,3,2)
    first=next(r for r in rows(e,sid) if r['status']=='A_ENVOYER' and r['communication_type']=='TEAMS_REMINDER_H2')
    valid,reason,_=teams_reminder_event_state(e,first,now=START_UTC-timedelta(minutes=2),enforce_due=True)
    assert not valid and reason=='SUPERSEDED_BY_SECOND_REMINDER'


def test_report_keeps_old_mail_sent_but_new_slot_uses_current_delay(tmp_path):
    e,oid,aid,pid,sid=setup(tmp_path)
    save(e,oid,5,2)
    old=rows(e,sid)
    execute(e,"UPDATE communication_events SET status='ENVOYE' WHERE id=:i",{'i':old[0]['id']})
    ns=report_slot(e,sid,'2030-06-13','12:00','13:00','test-admin','Report fictif')
    assert ns and ns!=sid
    assert one(e,'SELECT status FROM communication_events WHERE id=:id',{'id':old[0]['id']})['status']=='ENVOYE'
    assert all(r['status']!='A_ENVOYER' for r in rows(e,sid))
    after={r['communication_type']:r for r in rows(e,ns) if r['status']=='A_ENVOYER'}
    assert len(after)==2
    assert after['TEAMS_REMINDER_H2']['due_at'].endswith('55:00+00:00')
    assert after['TEAMS_REMINDER_H15']['due_at'].endswith('58:00+00:00')


def test_action_organization_overrides_global_reminder_schedule(tmp_path):
    e,oid,aid,pid,sid=setup(tmp_path)
    other=execute(e,"""INSERT INTO organizations(name,timezone,created_at,updated_at,
        online_reminder_first_minutes,online_reminder_second_minutes)
        VALUES('Autre organisme','Europe/Paris',:now,:now,9,4)""",{'now':utcnow_iso()})
    execute(e,'UPDATE actions SET organization_id=:o WHERE id=:a',{'o':other,'a':aid})
    synchronize_teams_reminders(e,action_id=aid,now=RealDateTime(2029,1,1,tzinfo=timezone.utc))
    assert get_online_reminder_preferences(e,aid)['online_reminder_first_minutes']==9
    assert get_online_reminder_preferences(e)['online_reminder_first_minutes']==120
    assert {r['due_at'] for r in rows(e,sid) if r['status']=='A_ENVOYER'}=={
        (START_UTC-timedelta(minutes=9)).isoformat(),(START_UTC-timedelta(minutes=4)).isoformat()}


def test_worker_configurable_advance_longer_than_old_3h_horizon(tmp_path,monkeypatch):
    e,oid,aid,pid,sid=setup(tmp_path)
    save(e,oid,600,30)
    # Remove pending events and let the automatic worker rebuild using the larger horizon.
    execute(e,"DELETE FROM communication_events WHERE communication_type IN ('TEAMS_REMINDER_H2','TEAMS_REMINDER_H15')")
    for name in ('_run_crm_callback_notifications','_quarantine_stale_sending','_quarantine_stale_quality',
                 '_quarantine_stale_client_transmissions','generate_due_final_bundles','_process_teams',
                 'refresh_pip_connector_runtime_status','refresh_ipip_connector_runtime_status','refresh_countersign_communications'):
        monkeypatch.setattr(worker,name,lambda *a,**k:0)
    monkeypatch.setattr(worker,'load_cfg',lambda:{'database':{'url':'sqlite:///:memory:'},'app':{'base_url':'https://example.invalid'}})
    monkeypatch.setattr(worker,'make_engine',lambda _:e)
    monkeypatch.setattr(worker,'init_db',lambda _:None)
    # Two minutes before the 10-hour advance deadline, the new horizon must queue both.
    clock_worker(monkeypatch,START_UTC-timedelta(minutes=602))
    assert worker.run_once()==0
    assert {r['communication_type'] for r in rows(e,sid) if r['status']=='A_ENVOYER'}=={
        'TEAMS_REMINDER_H2','TEAMS_REMINDER_H15'}


def test_dashboard_contains_both_minutes_and_timezones_without_auto_reset():
    src=(Path(__file__).resolve().parents[1]/'app.py').read_text('utf-8')
    assert "st.subheader('Paramètres régionaux et horaires')" in src
    assert 'Programmation des rappels – formations en ligne (Teams)' in src
    assert "number_input('Premier rappel (minutes avant)'" in src
    assert "number_input('Deuxième rappel (minutes avant)'" in src
    assert 'first_reminder_minutes=first_reminder,second_reminder_minutes=second_reminder' in src
    assert 'Aucun retour automatique aux valeurs habituelles' in src
