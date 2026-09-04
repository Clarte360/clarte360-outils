import os
from pathlib import Path
from db import make_engine, init_db, one, q
from services import (
    create_action, add_participant, add_trainer, assign_trainer,
    participant_pin_for_authorized_display, reset_participant_pin,
    create_trainer_password_reset, complete_trainer_password_reset,
    verify_trainer_login, create_trainer_report, trainer_reports,
    trainer_action_dashboard,
)


def engine(tmp_path):
    e=make_engine(f"sqlite:///{tmp_path/'lot1.db'}"); init_db(e); return e


def action_payload(no='LOT1'):
    return dict(action_no=no,title='Formation test',subtitle=None,nature='FORMATION',mode='PRESENTIEL',client_name='Client',client_type=None,group_code=None,planned_hours=7,expected_participants=1,admin_email='admin@example.org',trainer_name=None,trainer_email=None,location='Paris',notes=None,source='test')


def test_pin_recovery_and_regeneration_are_audited(tmp_path, monkeypatch):
    monkeypatch.setenv('CLARTE360_PIN_KEY','test-key-long-and-private')
    e=engine(tmp_path); aid=create_action(e,action_payload(),'admin')
    pid,pin=add_participant(e,aid,{'last_name':'DURAND','first_name':'Marie','email':'m@example.org'},'admin')
    assert participant_pin_for_authorized_display(e,pid,'trainer:1',aid)==pin
    newpin=reset_participant_pin(e,pid,'trainer:1')
    assert newpin!=pin
    assert participant_pin_for_authorized_display(e,pid,'trainer:1',aid)==newpin
    events=[x['event_type'] for x in q(e,'SELECT event_type FROM audit_log WHERE action_id=:a ORDER BY id',{'a':aid})]
    assert 'PARTICIPANT_PIN_VIEWED' in events and 'PARTICIPANT_PIN_RESET' in events


def test_password_reset_is_single_use(tmp_path):
    e=engine(tmp_path); tid=add_trainer(e,'Formateur Test','trainer@example.org','','admin')
    tr,token=create_trainer_password_reset(e,'trainer@example.org')
    assert tr['id']==tid and token
    ok,msg=complete_trainer_password_reset(e,token,'MotDePasseTresLong1!')
    assert ok
    assert verify_trainer_login(e,'trainer@example.org','MotDePasseTresLong1!')['id']==tid
    ok2,_=complete_trainer_password_reset(e,token,'AutreMotDePasseLong2!')
    assert not ok2


def test_trainer_reports_are_restricted_to_assigned_action(tmp_path):
    e=engine(tmp_path); aid=create_action(e,action_payload('A1'),'admin'); aid2=create_action(e,action_payload('A2'),'admin')
    tid=add_trainer(e,'Formateur Test','trainer@example.org','','admin'); assign_trainer(e,aid,tid,'admin')
    rid=create_trainer_report(e,aid,tid,'Incident','Salle fermée','Le site était inaccessible.',True)
    assert rid and len(trainer_reports(e,aid,tid))==1
    assert create_trainer_report(e,aid2,tid,'Observation','Interdit','Ne doit pas passer',False) is None
    assert one(e,"SELECT id FROM quality_issues WHERE action_id=:a AND issue_type='SIGNALEMENT_INTERVENANT'",{'a':aid})


def test_trainer_dashboard_only_for_assigned_action(tmp_path):
    e=engine(tmp_path); aid=create_action(e,action_payload('A1'),'admin'); aid2=create_action(e,action_payload('A2'),'admin')
    tid=add_trainer(e,'Formateur Test','trainer@example.org','','admin'); assign_trainer(e,aid,tid,'admin')
    assert trainer_action_dashboard(e,tid,aid) is not None
    assert trainer_action_dashboard(e,tid,aid2) is None


def test_no_streamlit_conditional_render_expression_remains():
    src=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
    assert 'st.success(msgm) if okm else st.warning(msgm)' not in src
    assert "(st.success(tf[1]) if tf[0]=='success' else st.warning(tf[1]))" not in src
    assert 'DeltaGenerator' not in src
