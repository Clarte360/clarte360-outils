from datetime import datetime, timezone
import json
import pytest
from db import make_engine, init_db, execute, one, q, utcnow_iso
from services import (create_action, add_slot, match_attendance_report_occurrence,
    store_teams_attendance_report, teams_occurrence_evidence, validate_no_action_slot_overlap,
    close_action)
from input_validation import InputValidationError
from signature_guard import signature_trace_is_valid


def seed(tmp_path):
    e=make_engine(f"sqlite:///{tmp_path/'h23.db'}"); init_db(e)
    aid=create_action(e,{'action_no':'H23-001','title':'Teams preuve','subtitle':None,'nature':'Formation','mode':'INTRA','client_name':'Client','client_type':'Professionnel','group_code':None,'planned_hours':2,'expected_participants':1,'admin_email':'a@b.fr','trainer_name':'Formateur','trainer_email':'f@b.fr','location':'Teams','notes':None,'source':'TEST'},'test')
    return e,aid


def test_same_action_overlap_blocked(tmp_path):
    e,aid=seed(tmp_path); add_slot(e,aid,'2026-09-15','19:30','21:30','admin')
    with pytest.raises(InputValidationError):
        add_slot(e,aid,'2026-09-15','20:00','21:00','admin')
    # Adjacent is allowed.
    add_slot(e,aid,'2026-09-15','21:30','22:00','admin')


def test_report_matching_is_limited_to_slot_plus_minus_30_minutes(tmp_path):
    e,aid=seed(tmp_path); sid=add_slot(e,aid,'2026-09-15','19:30','21:30','admin')
    now=utcnow_iso(); rid=execute(e,"INSERT INTO teams_action_rooms(action_id,organizer_upn,online_meeting_id,join_web_url,created_at,updated_at) VALUES(:a,'teams@clarte360.com','MID','url',:n,:n)",{'a':aid,'n':now})
    oid=execute(e,"INSERT INTO teams_occurrences(action_room_id,action_id,slot_id,scheduled_start_utc,scheduled_end_utc,status,created_at,updated_at) VALUES(:r,:a,:s,'2026-09-15T17:30:00+00:00','2026-09-15T19:30:00+00:00','PLANNED',:n,:n)",{'r':rid,'a':aid,'s':sid,'n':now})
    good={'id':'good','meetingStartDateTime':'2026-09-15T17:25:00Z','meetingEndDateTime':'2026-09-15T19:35:00Z'}
    bad={'id':'bad','meetingStartDateTime':'2026-09-15T10:00:00Z','meetingEndDateTime':'2026-09-15T11:00:00Z'}
    assert match_attendance_report_occurrence(e,aid,good)['id']==oid
    assert match_attendance_report_occurrence(e,aid,bad) is None


def test_graph_evidence_is_persisted_with_hash_and_unmatched_identity(tmp_path):
    e,aid=seed(tmp_path); sid=add_slot(e,aid,'2026-09-15','19:30','21:30','admin')
    now=utcnow_iso(); room=execute(e,"INSERT INTO teams_action_rooms(action_id,organizer_upn,online_meeting_id,join_web_url,created_at,updated_at) VALUES(:a,'teams@clarte360.com','MID','url',:n,:n)",{'a':aid,'n':now})
    execute(e,"INSERT INTO teams_occurrences(action_room_id,action_id,slot_id,scheduled_start_utc,scheduled_end_utc,status,created_at,updated_at) VALUES(:r,:a,:s,'2026-09-15T17:30:00+00:00','2026-09-15T19:30:00+00:00','PLANNED',:n,:n)",{'r':room,'a':aid,'s':sid,'n':now})
    rep={'id':'R1','meetingStartDateTime':'2026-09-15T17:29:00Z','meetingEndDateTime':'2026-09-15T19:31:00Z','totalParticipantCount':1}
    rec=[{'id':'anon','totalAttendanceInSeconds':3600,'role':'Attendee','identity':{'displayName':'Pseudo Test'},'attendanceIntervals':[{'durationInSeconds':3600,'joinDateTime':'2026-09-15T17:30:00Z','leaveDateTime':'2026-09-15T18:30:00Z'}]}]
    assert store_teams_attendance_report(e,aid,room,rep,rec)
    rr=one(e,"SELECT * FROM teams_attendance_reports WHERE report_id='R1'")
    ar=one(e,"SELECT * FROM teams_attendance_records WHERE report_row_id=:r",{'r':rr['id']})
    assert rr['raw_sha256'] and len(rr['raw_sha256'])==64
    assert ar['raw_sha256'] and len(ar['raw_sha256'])==64
    assert ar['participant_id'] is None and ar['display_name']=='Pseudo Test'
    assert teams_occurrence_evidence(e,aid)[0]['report']['report_id']=='R1'


def test_signature_guard_rejects_tap_and_accepts_real_trace():
    np=pytest.importorskip('numpy')
    blank=np.full((190,520,4),255,dtype='uint8')
    dot=blank.copy(); dot[90:96,250:256,:3]=0
    line=blank.copy();
    for x in range(120,340):
        y=80 + int(18*((x-120)%70)/70)
        line[y:y+4,x:x+3,:3]=0
    assert not signature_trace_is_valid(blank)
    assert not signature_trace_is_valid(dot)
    assert signature_trace_is_valid(line)


def test_closed_action_does_not_delete_cold_quality_configuration(tmp_path):
    e,aid=seed(tmp_path)
    execute(e,"UPDATE actions SET use_quality_cold=1,status='CLOTUREE' WHERE id=:a",{'a':aid})
    assert one(e,'SELECT use_quality_cold,status FROM actions WHERE id=:a',{'a':aid})=={'use_quality_cold':1,'status':'CLOTUREE'}
