from db import make_engine, init_db, one, execute, utcnow_iso
from services import (
    create_action, add_participant, add_slot, set_attendance_status,
    purge_participant, purge_action, purge_slot, add_trainer, assign_trainer,
    trainer_url, countersign_slot, can_issue_certificate
)

def seed(tmp_path):
    e=make_engine(f"sqlite:///{tmp_path/'v111.db'}"); init_db(e)
    aid=create_action(e,{'action_no':'V111-1','title':'Essai','subtitle':None,'nature':'Formation','mode':'INDIVIDUEL','client_name':None,'client_type':'Particulier','group_code':None,'planned_hours':1.75,'expected_participants':1,'admin_email':'a@b.fr','trainer_name':None,'trainer_email':None,'location':'ONLINE','notes':None,'source':'TEST'},'admin')
    pid,_=add_participant(e,aid,{'last_name':'BRIET','first_name':'Dominique','birth_date':'1966-02-23','email':'d@example.com'},'admin')
    sid=add_slot(e,aid,'2026-09-02','10:45','12:30','admin')
    return e,aid,pid,sid

def add_sig(e,pid,sid):
    execute(e,"INSERT INTO signatures(participant_id,slot_id,signed_at,signature_path,signature_sha256,signer_name,method,status) VALUES(:p,:s,:at,'','x','Dominique','EMAIL','VALIDE')",{'p':pid,'s':sid,'at':utcnow_iso()})

def test_signed_person_cannot_be_marked_absent(tmp_path):
    e,aid,pid,sid=seed(tmp_path); add_sig(e,pid,sid)
    ok,msg=set_attendance_status(e,pid,sid,'ABSENT','erreur','trainer')
    assert not ok and 'signature valide' in msg

def test_stale_absence_does_not_block_signed_certificate(tmp_path):
    e,aid,pid,sid=seed(tmp_path)
    set_attendance_status(e,pid,sid,'ABSENT','ancienne erreur','trainer')
    add_sig(e,pid,sid); countersign_slot(e,sid,'Formateur','f@example.com','trainer','certifie')
    ok,issues=can_issue_certificate(e,pid,require_closed=False)
    assert ok,issues

def test_hard_purge_participant_removes_evidence(tmp_path):
    e,aid,pid,sid=seed(tmp_path); add_sig(e,pid,sid)
    ok,msg=purge_participant(e,pid,'admin'); assert ok,msg
    assert one(e,'SELECT id FROM participants WHERE id=:p',{'p':pid}) is None
    assert one(e,'SELECT id FROM signatures WHERE participant_id=:p',{'p':pid}) is None

def test_hard_purge_slot_removes_evidence(tmp_path):
    e,aid,pid,sid=seed(tmp_path); add_sig(e,pid,sid)
    ok,msg=purge_slot(e,sid,'admin'); assert ok,msg
    assert one(e,'SELECT id FROM slots WHERE id=:s',{'s':sid}) is None
    assert one(e,'SELECT id FROM signatures WHERE slot_id=:s',{'s':sid}) is None

def test_hard_purge_action_removes_children(tmp_path):
    e,aid,pid,sid=seed(tmp_path); add_sig(e,pid,sid)
    ok,msg=purge_action(e,aid,'admin'); assert ok,msg
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':aid}) is None
    assert one(e,'SELECT id FROM participants WHERE action_id=:a',{'a':aid}) is None
    assert one(e,'SELECT id FROM slots WHERE action_id=:a',{'a':aid}) is None

def test_trainer_registry_assignment_and_link(tmp_path):
    e,aid,pid,sid=seed(tmp_path)
    tid=add_trainer(e,'Formateur Test','f@example.com','0600000000','admin')
    assign_trainer(e,aid,tid,'admin')
    a=one(e,'SELECT trainer_id,trainer_name,trainer_email FROM actions WHERE id=:a',{'a':aid})
    assert a['trainer_id']==tid and a['trainer_name']=='Formateur Test'
    u=trainer_url(e,aid,'https://emargements.clarte360.com')
    assert 'trainer_token=' in u
