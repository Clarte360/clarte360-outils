from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from db import make_engine, init_db, one, q
from services import (
    create_action, add_trainer, assign_trainer, add_participant, add_slot,
    set_generic_action_module, create_or_sync_teams_room,
    trainer_microsoft_identity, set_trainer_microsoft_email,
    request_trainer_microsoft_identity_creation, teams_next_meeting,
    teams_unmatched_attendance, confirm_teams_attendance_identity,
    store_teams_attendance_report, teams_occurrences,
)
from worker import _sync_teams_trainer_identities


class FakeGraph:
    def __init__(self, existing=None, guest_invites_enabled=True):
        self.cfg={
            'organizer_user_id':'org-id',
            'organizer_upn':'teams@clarte360.com',
            'guest_invites_enabled':guest_invites_enabled,
        }
        self.existing=existing
        self.searches=[]
        self.invites=[]
        self.created=[]
        self.updated=[]
    def create_online_meeting(self, subject, start_iso, end_iso, attendees=None):
        self.created.append((subject,start_iso,end_iso,attendees))
        return {'id':'meeting-i9c','joinWebUrl':'https://teams.microsoft.com/l/meetup-join/i9c'}
    def update_online_meeting(self, meeting_id, patch):
        self.updated.append((meeting_id,patch)); return {}
    def find_user_by_email(self,email):
        self.searches.append(email)
        return self.existing
    def invite_guest(self,email,redirect_url,send_invitation_message=True,display_name=None):
        self.invites.append(email)
        return {'id':'inv-1','invitedUser':{'id':'guest-i9c','mail':email}}


def seed(no='I9C-001', trainer_email='external@example.net'):
    e=make_engine('sqlite:///:memory:'); init_db(e)
    aid=create_action(e,{
        'action_no':no,'title':'Action I9-C','subtitle':None,'nature':'FORMATION','mode':'INDIVIDUEL',
        'client_name':'Client','client_type':'Entreprise','group_code':None,'planned_hours':3,
        'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Online','notes':None,'source':'TEST'
    },'test')
    tid=add_trainer(e,'Intervenant Test',trainer_email,'','test'); assign_trainer(e,aid,tid,'test')
    pid,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01','email':'anne@example.org'},'test')
    sid=add_slot(e,aid,'2026-10-15','09:00','10:30','test')
    set_generic_action_module(e,aid,'TEAMS',True,'admin')
    return e,aid,tid,pid,sid


def test_i9c_trainer_permanent_microsoft_identity_fields_are_additive():
    e,aid,tid,pid,sid=seed()
    cols={x['name'] for x in q(e,'PRAGMA table_info(trainers)')}
    for name in ('microsoft_email','entra_user_id','entra_status','entra_last_verified_at','entra_creation_requested_at','entra_creation_requested_by'):
        assert name in cols
    ident=trainer_microsoft_identity(e,tid)
    assert ident['entra_status']=='UNCHECKED'
    set_trainer_microsoft_email(e,tid,'personne@outlook.com','admin')
    ident=trainer_microsoft_identity(e,tid)
    assert ident['microsoft_email']=='personne@outlook.com' and ident['entra_user_id'] is None


def test_i9c_worker_searches_existing_entra_identity_and_never_creates_silently():
    e,aid,tid,pid,sid=seed('I9C-NOSILENT')
    create_or_sync_teams_room(e,aid,FakeGraph(),'test')
    fake=FakeGraph(existing=None,guest_invites_enabled=True)
    _sync_teams_trainer_identities(e,fake,aid,'https://app.example.org')
    assert fake.searches == ['external@example.net']
    assert fake.invites == []
    assert trainer_microsoft_identity(e,tid)['entra_status']=='NOT_FOUND'


def test_i9c_explicit_creation_request_searches_again_before_guest_invite():
    e,aid,tid,pid,sid=seed('I9C-EXPLICIT')
    create_or_sync_teams_room(e,aid,FakeGraph(),'test')
    request_trainer_microsoft_identity_creation(e,tid,'admin@example.org')
    fake=FakeGraph(existing=None,guest_invites_enabled=True)
    _sync_teams_trainer_identities(e,fake,aid,'https://app.example.org')
    assert fake.searches == ['external@example.net','external@example.net']
    assert fake.invites == ['external@example.net']
    ident=trainer_microsoft_identity(e,tid)
    assert ident['entra_user_id']=='guest-i9c' and ident['entra_status']=='INVITED'


def test_i9c_existing_identity_prevents_guest_creation_even_after_request():
    e,aid,tid,pid,sid=seed('I9C-FOUND')
    create_or_sync_teams_room(e,aid,FakeGraph(),'test')
    request_trainer_microsoft_identity_creation(e,tid,'admin@example.org')
    fake=FakeGraph(existing={'id':'existing-entra','mail':'external@example.net'},guest_invites_enabled=True)
    _sync_teams_trainer_identities(e,fake,aid,'https://app.example.org')
    assert fake.invites == []
    assert trainer_microsoft_identity(e,tid)['entra_user_id']=='existing-entra'
    assert trainer_microsoft_identity(e,tid)['entra_status']=='VERIFIED'


def test_i9c_next_meeting_uses_business_slot_not_technical_id():
    e,aid,tid,pid,sid=seed('I9C-NEXT')
    create_or_sync_teams_room(e,aid,FakeGraph(),'test')
    nxt=teams_next_meeting(e,aid,datetime(2026,10,1,tzinfo=ZoneInfo('UTC')))
    assert nxt['slot_date']=='2026-10-15' and nxt['start_time']=='09:00' and nxt['end_time']=='10:30'


def test_i9c_unknown_teams_email_is_never_blindly_attributed_and_can_be_confirmed():
    e,aid,tid,pid,sid=seed('I9C-ATT')
    room=create_or_sync_teams_room(e,aid,FakeGraph(),'test')
    occ=next(x for x in teams_occurrences(e,aid) if x['slot_id']==sid)
    report={'id':'report-i9c','meetingStartDateTime':occ['scheduled_start_utc'],'meetingEndDateTime':occ['scheduled_end_utc']}
    records=[{'emailAddress':'anne.other@outlook.com','identity':{'displayName':'Anne DUPONT'},'attendanceIntervals':[{'joinDateTime':occ['scheduled_start_utc'],'leaveDateTime':occ['scheduled_end_utc'],'durationInSeconds':5400}]}]
    store_teams_attendance_report(e,aid,room['id'],report,records,'test')
    unmatched=teams_unmatched_attendance(e,aid)
    assert len(unmatched)==1 and unmatched[0]['email']=='anne.other@outlook.com'
    rid=unmatched[0]['attendance_record_id']
    assert one(e,'SELECT participant_id FROM teams_attendance_records WHERE id=:i',{'i':rid})['participant_id'] is None
    confirm_teams_attendance_identity(e,rid,pid,'admin')
    assert one(e,'SELECT participant_id FROM teams_attendance_records WHERE id=:i',{'i':rid})['participant_id']==pid


def test_i9c_user_interfaces_do_not_expose_meeting_id_or_entra_id_to_portals():
    text=Path('app.py').read_text(encoding='utf-8')
    trainer_block=text[text.index('with tab_teams:'):text.index('with tab_em:')]
    beneficiary=text[text.index("with tabs[3]:"):text.index("with tabs[4]:")]
    assert 'Meeting ID' not in trainer_block and 'Entra ID' not in trainer_block
    assert 'Meeting ID' not in beneficiary and 'Entra ID' not in beneficiary and 'COORGANIZER' not in beneficiary
