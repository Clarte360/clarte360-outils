from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from db import make_engine, init_db, one, q, execute
from services import (
    create_action, add_participant, add_slot, add_trainer, assign_trainer,
    set_generic_action_module, action_module_enabled, action_module,
    create_or_sync_teams_room, teams_room, teams_occurrences, teams_roles,
    store_teams_attendance_report, teams_attendance_reconciliation,
)
from graph_client import graph_config_from_mapping, graph_config_missing


class FakeGraph:
    def __init__(self):
        self.cfg={
            'organizer_user_id':'organizer-object-id',
            'organizer_upn':'teams@clarte360.com',
            'guest_invites_enabled':True,
        }
        self.created=[]; self.updated=[]; self.invited=[]
    def create_online_meeting(self, subject, start_iso, end_iso, attendees=None):
        self.created.append((subject,start_iso,end_iso,attendees))
        return {'id':'meeting-001','joinWebUrl':'https://teams.microsoft.com/l/meetup-join/test','subject':subject}
    def update_online_meeting(self, meeting_id, patch):
        self.updated.append((meeting_id,patch)); return {}
    def invite_guest(self,email,redirect_url,send_invitation_message=True,display_name=None):
        self.invited.append(email);return {'id':'invite-1','invitedUser':{'id':'guest-1'}}


def seed(no='V3I7-001'):
    e=make_engine('sqlite:///:memory:');init_db(e)
    aid=create_action(e,{
        'action_no':no,'title':'Action Teams','subtitle':None,'nature':'FORMATION','mode':'INDIVIDUEL',
        'client_name':'Client','client_type':'Entreprise','group_code':None,'planned_hours':3,
        'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Online','notes':None,'source':'TEST'
    },'test')
    t=add_trainer(e,'Intervenant externe','external@example.net','','test');assign_trainer(e,aid,t,'test')
    p,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'anne@example.org'},'test')
    past=add_slot(e,aid,'2026-08-15','09:00','10:30','test')
    future=add_slot(e,aid,'2026-10-15','09:00','10:30','test')
    return e,aid,t,p,past,future


def test_i7_schema_is_additive_and_teams_is_not_inferred_from_online_mode():
    e,aid,t,p,past,future=seed()
    for table in ('teams_action_rooms','teams_occurrences','teams_participant_roles','teams_attendance_reports','teams_attendance_records','teams_sync_events'):
        assert one(e,"SELECT name FROM sqlite_master WHERE type='table' AND name=:n",{'n':table})
    assert not action_module_enabled(e,aid,'TEAMS')
    assert teams_room(e,aid) is None


def test_i7_activation_is_prospective_from_next_future_slot():
    e,aid,t,p,past,future=seed('V3I7-EFF')
    eff=set_generic_action_module(e,aid,'TEAMS',True,'admin')
    assert eff.startswith('2026-10-15T09:00:00')
    mod=action_module(e,aid,'TEAMS'); assert mod['enabled']==1 and mod['effective_from']==eff
    fake=FakeGraph(); create_or_sync_teams_room(e,aid,fake,'test')
    occ=teams_occurrences(e,aid)
    assert [x['slot_id'] for x in occ if x['status']!='OUT_OF_SCOPE']==[future]
    assert all(x['slot_id']!=past or x['status']=='OUT_OF_SCOPE' for x in occ)


def test_i7_stable_action_link_is_created_once_and_reused():
    e,aid,t,p,past,future=seed('V3I7-LINK')
    set_generic_action_module(e,aid,'TEAMS',True,'admin')
    fake=FakeGraph()
    room=create_or_sync_teams_room(e,aid,fake,'test')
    assert room['online_meeting_id']=='meeting-001'
    assert room['join_web_url'].startswith('https://teams.microsoft.com/')
    assert room['strategy']=='STABLE_ACTION_LINK'
    assert len(fake.created)==1
    room2=create_or_sync_teams_room(e,aid,fake,'test')
    assert room2['online_meeting_id']=='meeting-001'
    assert len(fake.created)==1 and len(fake.updated)==1


def test_i7_multi_trainer_roles_follow_slot_assignments():
    e,aid,t,p,past,future=seed('V3I7-ROLE')
    t2=add_trainer(e,'Co intervenant','co@example.net','','test')
    from services import assign_slot_trainer
    assign_slot_trainer(e,future,t2,'admin','CO_INTERVENANT')
    set_generic_action_module(e,aid,'TEAMS',True,'admin')
    create_or_sync_teams_room(e,aid,FakeGraph(),'test')
    roles=teams_roles(e,aid,future)
    by_email={x['email']:x for x in roles}
    assert by_email['external@example.net']['role']=='COORGANIZER'
    assert by_email['co@example.net']['role']=='PRESENTER'


def test_i7_attendance_report_is_mapped_to_occurrence_and_never_replaces_signature():
    e,aid,t,p,past,future=seed('V3I7-ATT')
    set_generic_action_module(e,aid,'TEAMS',True,'admin');fake=FakeGraph();room=create_or_sync_teams_room(e,aid,fake,'test')
    occ=next(x for x in teams_occurrences(e,aid) if x['slot_id']==future)
    report={'id':'report-1','meetingStartDateTime':occ['scheduled_start_utc'],'meetingEndDateTime':occ['scheduled_end_utc']}
    records=[{'emailAddress':'anne@example.org','role':'attendee','identity':{'displayName':'Anne DUPONT'},'attendanceIntervals':[{'joinDateTime':occ['scheduled_start_utc'],'leaveDateTime':occ['scheduled_end_utc'],'durationInSeconds':5400}]}]
    assert store_teams_attendance_report(e,aid,room['id'],report,records,'test') is True
    assert store_teams_attendance_report(e,aid,room['id'],report,records,'test') is False
    rec=next(x for x in teams_attendance_reconciliation(e,aid) if x['slot_id']==future and x['participant_id']==p)
    assert rec['teams_present'] is True and rec['teams_seconds']==5400
    assert rec['signed'] is False and rec['anomaly'] is True


def test_i7_disabling_module_preserves_existing_room_and_reports():
    e,aid,t,p,past,future=seed('V3I7-DIS')
    set_generic_action_module(e,aid,'TEAMS',True,'admin');room=create_or_sync_teams_room(e,aid,FakeGraph(),'test')
    set_generic_action_module(e,aid,'TEAMS',False,'admin')
    assert not action_module_enabled(e,aid,'TEAMS')
    assert teams_room(e,aid)['id']==room['id']
    assert all(x['status']=='DISABLED' for x in teams_occurrences(e,aid) if not x.get('attendance_report_id'))


def test_i7_secret_configuration_uses_certificate_and_no_secret_value_in_code(tmp_path):
    cfg=graph_config_from_mapping({'microsoft_graph':{
        'enabled':True,'tenant_id':'tenant','client_id':'client','organizer_user_id':'user',
        'organizer_upn':'teams@clarte360.com','certificate_path':str(tmp_path/'missing.pem'),'certificate_thumbprint':'AA BB'
    }})
    assert cfg['certificate_thumbprint']=='AABB'
    assert 'certificate_path (fichier introuvable)' in graph_config_missing(cfg)
    txt=Path('graph_client.py').read_text(encoding='utf-8')
    assert 'client_secret' not in txt
    assert 'private_key' in txt and 'certificate_thumbprint' in txt


def test_i7_worker_runs_graph_independently_of_smtp():
    txt=Path('worker.py').read_text(encoding='utf-8')
    teams_pos=txt.index('teams_changed=_process_teams')
    smtp_pos=txt.index("if not smtp.get('enabled'): return teams_changed")
    assert teams_pos < smtp_pos
    assert "OnlineMeetingArtifact" not in txt  # permissions live in documentation, never as runtime secrets
