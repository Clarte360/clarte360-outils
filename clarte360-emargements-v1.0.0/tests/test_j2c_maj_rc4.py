from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from db import make_engine, init_db, execute, q, one, utcnow_iso
from services import (
    create_action, add_participant, add_slot, add_trainer, assign_trainer,
    ensure_default_organization, refresh_all_worker_events,
)


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); ensure_default_organization(e); return e


def mk_action(e,no='RC4-001'):
    aid=create_action(e,dict(action_no=no,title='Formation Teams',subtitle=None,nature='FORMATION',mode='DISTANCIEL',client_name='Client',client_type='Entreprise',group_code=None,planned_hours=1,expected_participants=1,admin_email='admin@example.org',trainer_name=None,trainer_email=None,location='Teams',notes=None,source='TEST'),'test')
    execute(e,"UPDATE actions SET status='ACTIVE' WHERE id=:a",{'a':aid})
    execute(e,"INSERT INTO action_modules(action_id,module_code,enabled,enabled_at,enabled_by,created_at,updated_at) VALUES(:a,'TEAMS',1,:n,'test',:n,:n)",{'a':aid,'n':utcnow_iso()})
    return aid


def test_refresh_all_worker_events_creates_teams_reminders_and_is_idempotent():
    e=eng(); aid=mk_action(e)
    tid=add_trainer(e,'Dominique BRIET','dbriet@clarte360.com','','test'); assign_trainer(e,aid,tid,'test')
    pid,_=add_participant(e,aid,{'last_name':'PAQUETTE','first_name':'Quentin','birth_date':'1990-01-01','email':'q@example.org'},'test')
    future=datetime.now(ZoneInfo('Europe/Paris'))+timedelta(days=2)
    sid=add_slot(e,aid,future.date().isoformat(),future.strftime('%H:%M'),(future+timedelta(hours=1)).strftime('%H:%M'),'test')
    r1=refresh_all_worker_events(e,'https://emargements.clarte360.com','Europe/Paris','admin')
    assert r1['actions']==1
    rows=q(e,"SELECT * FROM communication_events WHERE slot_id=:s AND communication_type IN ('TEAMS_REMINDER_H2','TEAMS_REMINDER_H15')",{'s':sid})
    assert len(rows)==4
    assert {x['recipient_email'] for x in rows}=={'q@example.org','dbriet@clarte360.com'}
    refresh_all_worker_events(e,'https://emargements.clarte360.com','Europe/Paris','admin')
    assert len(q(e,"SELECT * FROM communication_events WHERE slot_id=:s AND communication_type IN ('TEAMS_REMINDER_H2','TEAMS_REMINDER_H15')",{'s':sid}))==4


def test_refresh_all_worker_events_reactivates_old_unsupported_reminder():
    e=eng(); aid=mk_action(e,'RC4-002')
    tid=add_trainer(e,'Dominique BRIET','dbriet@clarte360.com','','test'); assign_trainer(e,aid,tid,'test')
    pid,_=add_participant(e,aid,{'last_name':'PAQUETTE','first_name':'Quentin','birth_date':'1990-01-01','email':'q@example.org'},'test')
    future=datetime.now(ZoneInfo('Europe/Paris'))+timedelta(days=2)
    sid=add_slot(e,aid,future.date().isoformat(),future.strftime('%H:%M'),(future+timedelta(hours=1)).strftime('%H:%M'),'test')
    execute(e,"""INSERT INTO communication_events(action_id,participant_id,slot_id,communication_type,recipient_email,trigger_mode,status,due_at,attempts,last_error,created_at,updated_at)
      VALUES(:a,:p,:s,'TEAMS_REMINDER_H2','q@example.org','AUTO','ANNULE',:d,1,'Type de communication non géré par le worker',:n,:n)""",{'a':aid,'p':pid,'s':sid,'d':utcnow_iso(),'n':utcnow_iso()})
    refresh_all_worker_events(e,'https://emargements.clarte360.com','Europe/Paris','admin')
    row=one(e,"SELECT * FROM communication_events WHERE action_id=:a AND participant_id=:p AND slot_id=:s AND communication_type='TEAMS_REMINDER_H2' ORDER BY id DESC LIMIT 1",{'a':aid,'p':pid,'s':sid})
    assert row['status']=='A_ENVOYER' and row['last_error'] is None


def test_app_keeps_non_pip_external_tools_autonomous_and_unique_document_keys():
    src=Path(__file__).resolve().parents[1].joinpath('app.py').read_text(encoding='utf-8')
    assert "elif ctx.get('base_url')" in src
    assert "L’outil s’ouvre ensuite avec son propre système d’accès et de sauvegarde" in src
    assert "key=f\"bdl_{key_prefix}_{d['id']}\"" in src
    assert "tr_csig_rc4_" in src
