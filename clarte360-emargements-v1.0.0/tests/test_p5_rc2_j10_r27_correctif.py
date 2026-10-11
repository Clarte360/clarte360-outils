"""J10 / R27 regressions: demo SQLite and SMTP stub ONLY. Previously failed before J10 corrective; re-run as regression guards.

Move into official tests only after adapting paths if desired. Never connects to VPS/SMTP.
"""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

import pytest
from db import make_engine,init_db,execute,q,one,utcnow_iso
from services import create_action,add_participant,add_slot,report_slot,refresh_all_worker_events,ensure_default_organization
import worker

@pytest.fixture
def rescheduled(tmp_path):
    engine=make_engine('sqlite:///'+str(tmp_path/'r27_fictive.sqlite3'))
    init_db(engine);ensure_default_organization(engine)
    aid=create_action(engine,dict(action_no='J10-R27-FICTIF',title='Essai fictif de seance deplacee',
        subtitle=None,nature='FORMATION',mode='DISTANCIEL',client_name='Entreprise fictive',client_type='Entreprise',
        group_code=None,planned_hours=1,expected_participants=1,admin_email='test@example.invalid',
        trainer_name=None,trainer_email=None,location='En ligne',notes=None,source='RECETTE_J10_FICTIVE'),'j10')
    execute(engine,"UPDATE actions SET status='ACTIVE' WHERE id=:a",{'a':aid})
    execute(engine,"INSERT INTO action_modules(action_id,module_code,enabled,enabled_at,enabled_by,created_at,updated_at) VALUES(:a,'TEAMS',1,:n,'j10',:n,:n)",{'a':aid,'n':utcnow_iso()})
    add_participant(engine,aid,dict(last_name='TEST',first_name='Fictif',email='nobody@example.invalid'),'j10')
    start=datetime.now(ZoneInfo('Europe/Paris'))+timedelta(minutes=180)
    end=start+timedelta(hours=1)
    old=add_slot(engine,aid,start.date().isoformat(),start.strftime('%H:%M'),end.strftime('%H:%M'),'j10')
    refresh_all_worker_events(engine,'https://example.invalid','Europe/Paris','j10')
    assert q(engine,"SELECT id FROM communication_events WHERE slot_id=:s AND communication_type='TEAMS_REMINDER_H2'",{'s':old})
    newstart=start+timedelta(days=2)
    newend=end+timedelta(days=2)
    new=report_slot(engine,old,newstart.date().isoformat(),newstart.strftime('%H:%M'),newend.strftime('%H:%M'),'j10','Décalage fictif')
    assert new and one(engine,'SELECT status FROM slots WHERE id=:s',{'s':old})['status']=='REPORTE'
    yield engine,old,start
    engine.dispose()

def fake_send(engine,monkeypatch):
    sent=[]
    monkeypatch.setattr(worker,'send_mail',lambda cfg,recipient,subject,body:sent.append({'subject':subject,'body':body}))
    worker._run_communication_events(engine,{},'https://example.invalid')
    return sent

def test_r27_old_teams_reminder_must_not_send_after_report(rescheduled,monkeypatch):
    engine,old,start=rescheduled
    # Simulate an old queued reminder resurrected after a concurrent report/legacy replay.
    execute(engine,"UPDATE communication_events SET status='A_ENVOYER',due_at='2000-01-01T00:00:00+00:00' WHERE slot_id=:s AND communication_type='TEAMS_REMINDER_H2'",{'s':old})
    mails=fake_send(engine,monkeypatch)
    obsolete=[mail for mail in mails if 'Rappel séance' in mail['subject'] and start.date().isoformat() in mail['body'] and start.strftime('%H:%M') in mail['body']]
    assert not obsolete, 'Un rappel Teams pour un créneau marqué REPORTE a été envoyé malgré le report.'

def test_r27_old_attendance_email_event_is_cancelled(rescheduled):
    engine,old,start=rescheduled
    statuses=q(engine,"SELECT event_type,status FROM email_events WHERE slot_id=:s AND event_type='INITIAL'",{'s':old})
    assert all(e['status'] not in ('PENDING','SENDING') for e in statuses), 'Demande d émargement de la séance REPORTÉE encore en attente.'

def test_r27_planning_confirmation_excludes_reported_slot(rescheduled,monkeypatch):
    engine,old,start=rescheduled
    mails=fake_send(engine,monkeypatch)
    confirmations=[mail for mail in mails if 'Confirmation de votre planning' in mail['subject']]
    assert confirmations, 'Précondition : confirmation fictive émise dans le scénario.'
    assert all(start.date().isoformat() not in x['body'] or start.strftime('%H:%M') not in x['body'] for x in confirmations), 'Confirmation contient la séance historique reportée.'
