from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest

from db import make_engine, init_db, q, one, execute
from services import (
    create_action, add_participant, add_slot, add_trainer, assign_trainer, assign_slot_trainer,
    create_beneficiary, link_participant_to_beneficiary,
    seed_tool_catalog, upsert_tool_catalog, set_action_tools_allowed, action_allowed_tools,
    create_tool_prescription, set_action_trainer_prescription_permission,
    cancel_tool_prescription_admin, prescription_events,
    store_document, list_action_documents, delete_document_reference,
    set_generic_action_module, create_or_sync_teams_room, refresh_teams_reminder_communications,
)


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); seed_tool_catalog(e); return e


def action(e,no='J1-001'):
    aid=create_action(e,{
        'action_no':no,'title':'Jalon 1 AB','subtitle':None,'nature':'FORMATION','mode':'INTRA',
        'client_name':'Client','client_type':'Entreprise','group_code':None,'planned_hours':3,
        'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Teams','notes':None,'source':'TEST'
    },'test')
    execute(e,"UPDATE actions SET prestation_type='FORMATION',status='ACTIVE' WHERE id=:a",{'a':aid})
    return aid


def linked_beneficiary(e,aid,email='anne@example.org'):
    pid,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':email},'test')
    bid=create_beneficiary(e,'DUPONT','Anne','1990-01-01',email,actor='test')
    link_participant_to_beneficiary(e,pid,bid,'test')
    return pid,bid


def test_j1_tools_selection_is_atomic_persistent_and_server_enforces_trainer_permission():
    e=eng(); aid=action(e); pid,bid=linked_beneficiary(e,aid)
    for code in ('J1_T1','J1_T2','J1_T3'):
        upsert_tool_catalog(e,{'tool_code':code,'name':code,'base_url':'https://example.org/'+code,
                               'launch_type':'HUB_REDIRECT','compatible_prestations':['FORMATION']},'admin')
    set_action_tools_allowed(e,aid,{'J1_T1','J1_T2','J1_T3'},'admin')
    assert {x['tool_code'] for x in action_allowed_tools(e,aid)}=={'J1_T1','J1_T2','J1_T3'}
    # Same DB truth after another init_db, equivalent to a rerun/F5/migration pass.
    init_db(e)
    assert {x['tool_code'] for x in action_allowed_tools(e,aid)}=={'J1_T1','J1_T2','J1_T3'}

    tid=add_trainer(e,'Coach','coach@example.org','','admin'); assign_trainer(e,aid,tid,'admin')
    with pytest.raises(ValueError,match='pas autorisé'):
        create_tool_prescription(e,'J1_T1',bid,aid,pid,prescriber_type='TRAINER',prescriber_id=tid,
                                 prescriber_role='INTERVENANT',actor='trainer')
    set_action_trainer_prescription_permission(e,aid,tid,True,'admin')
    pr=create_tool_prescription(e,'J1_T1',bid,aid,pid,prescriber_type='TRAINER',prescriber_id=tid,
                                prescriber_role='INTERVENANT',actor='trainer')
    assert pr['status']=='A_FAIRE'
    ok,msg=cancel_tool_prescription_admin(e,pr['prescription_id'],'admin@example.org','admin@example.org')
    assert ok and not msg
    assert one(e,'SELECT status FROM tool_prescriptions WHERE prescription_id=:p',{'p':pr['prescription_id']})['status']=='ANNULE'
    assert any(x['event_type']=='STATUS_CHANGED' for x in prescription_events(e,pr['prescription_id']))
    assert one(e,"SELECT id FROM audit_log WHERE event_type='TOOL_PRESCRIPTION_ADMIN_CANCELLED'")


def test_j1_documents_keep_origin_hash_and_protect_regulatory_evidence():
    e=eng(); aid=action(e,'J1-DOC')
    rid1,h1,_=store_document(e,b'{"ok":true}','result.json','RESULTAT_APP','admin',action_id=aid,
                             origin='ADMIN',allowed_extensions={'.json'})
    rid2,h2,_=store_document(e,b'%PDF-1.4 test','preuve.pdf','PREUVE','system',action_id=aid,
                             origin='SYSTEME',regulatory=True,immutable_reason='PREUVE_REGLEMENTAIRE',allowed_extensions={'.pdf'})
    docs={x['id']:x for x in list_action_documents(e,aid)}
    assert docs[rid1]['origin']=='ADMIN' and docs[rid1]['sha256']==h1
    assert docs[rid2]['origin']=='SYSTEME' and docs[rid2]['sha256']==h2 and docs[rid2]['regulatory']==1
    assert delete_document_reference(e,rid1,'admin') is True
    assert delete_document_reference(e,rid2,'admin') is False
    assert one(e,'SELECT deleted_at FROM document_references WHERE id=:i',{'i':rid2})['deleted_at'] is None


class FakeGraph:
    def __init__(self):
        self.cfg={'organizer_user_id':'u','organizer_upn':'teams@clarte360.com','guest_invites_enabled':False}
    def create_online_meeting(self, subject, start_iso, end_iso, attendees=None):
        return {'id':'meeting-j1','joinWebUrl':'https://teams.microsoft.com/l/meetup-join/j1','subject':subject}
    def update_online_meeting(self, meeting_id, patch): return {}


def test_j1_teams_h2_h15_are_idempotent_include_all_slot_trainers_and_recalculate():
    e=eng(); aid=action(e,'J1-TEAMS'); pid,_=linked_beneficiary(e,aid)
    t1=add_trainer(e,'Animateur','anim@example.org','','admin'); assign_trainer(e,aid,t1,'admin')
    sid=add_slot(e,aid,'2026-09-20','09:00','10:30','admin')
    t2=add_trainer(e,'Coanimatrice','co@example.org','','admin'); assign_slot_trainer(e,sid,t2,'admin','CO_INTERVENANT')
    set_generic_action_module(e,aid,'TEAMS',True,'admin',effective_from='2026-09-20T09:00:00+02:00')
    create_or_sync_teams_room(e,aid,FakeGraph(),'test')

    now=datetime(2026,9,20,4,0,tzinfo=ZoneInfo('UTC'))
    refresh_teams_reminder_communications(e,now=now)
    rows=q(e,"SELECT * FROM communication_events WHERE slot_id=:s AND communication_type LIKE 'TEAMS_REMINDER_%'",{'s':sid})
    # 1 beneficiary + 2 trainers, twice (H-2 and H-15)
    assert len(rows)==6
    assert len({x['idempotency_key'] for x in rows})==6
    assert {x['recipient_email'] for x in rows}=={'anne@example.org','anim@example.org','co@example.org'}
    refresh_teams_reminder_communications(e,now=now)
    assert one(e,"SELECT COUNT(*) n FROM communication_events WHERE slot_id=:s AND communication_type LIKE 'TEAMS_REMINDER_%'",{'s':sid})['n']==6

    old_due={x['id']:x['due_at'] for x in rows}
    ok,_=__import__('services').safe_update_slot(e,sid,{'slot_date':'2026-09-20','start_time':'10:00','end_time':'11:30',
        'send_offset_min':-10,'reminder1_offset_min':20,'reminder2_offset_min':120,'close_offset_min':1440},'admin')
    assert ok
    refresh_teams_reminder_communications(e,now=now)
    changed=q(e,"SELECT id,due_at FROM communication_events WHERE slot_id=:s AND communication_type LIKE 'TEAMS_REMINDER_%'",{'s':sid})
    assert any(x['due_at']!=old_due[x['id']] for x in changed)

    execute(e,"UPDATE slots SET status='ANNULE' WHERE id=:s",{'s':sid})
    refresh_teams_reminder_communications(e,now=now)
    assert one(e,"SELECT COUNT(*) n FROM communication_events WHERE slot_id=:s AND communication_type LIKE 'TEAMS_REMINDER_%' AND status='ANNULE'",{'s':sid})['n']==6


def test_j1_worker_teams_reminder_contains_join_and_portal_links(monkeypatch):
    import worker
    e=eng(); aid=action(e,'J1-MAIL'); pid,_=linked_beneficiary(e,aid)
    t=add_trainer(e,'Animateur','anim@example.org','','admin'); assign_trainer(e,aid,t,'admin')
    sid=add_slot(e,aid,'2026-09-20','09:00','10:30','admin')
    set_generic_action_module(e,aid,'TEAMS',True,'admin',effective_from='2026-09-20T09:00:00+02:00')
    create_or_sync_teams_room(e,aid,FakeGraph(),'test')
    refresh_teams_reminder_communications(e,now=datetime(2026,9,20,4,0,tzinfo=ZoneInfo('UTC')))
    execute(e,"UPDATE communication_events SET due_at='2000-01-01T00:00:00+00:00' WHERE slot_id=:s AND communication_type='TEAMS_REMINDER_H2' AND participant_id=:p",{'s':sid,'p':pid})
    sent=[]; monkeypatch.setattr(worker,'send_mail',lambda cfg,to,subject,body: sent.append((to,subject,body)))
    assert worker._run_communication_events(e,{'enabled':True,'from_email':'x@example.org'},'https://emargements.clarte360.com')>=1
    reminder=next(x for x in sent if x[0]=='anne@example.org' and 'Teams dans 2 heures' in x[1])
    assert 'REJOINDRE TEAMS' in reminder[2] and 'MON ESPACE BÉNÉFICIAIRE' in reminder[2]
    assert 'pas encore activé' in reminder[2]


def test_j1_teams_wording_never_turns_unmatched_graph_into_an_absence():
    txt=Path('app.py').read_text(encoding='utf-8')
    assert "'Non observée'" not in txt
    assert 'Rapprochement non établi' in txt


def test_j1_document_migration_is_idempotent():
    e=make_engine('sqlite:///:memory:'); init_db(e); init_db(e)
    cols={x['name'] for x in q(e,'PRAGMA table_info(document_references)')}
    assert {'origin','regulatory','immutable_reason'} <= cols
