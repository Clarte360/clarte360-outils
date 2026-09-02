from pathlib import Path
from db import make_engine,init_db,one
from services import create_action,add_participant,add_slot,set_attendance_status,create_catchup_slot,safe_update_slot,countersign_slot,can_issue_certificate

def seed(tmp_path):
    e=make_engine(f"sqlite:///{tmp_path/'v11.db'}");init_db(e)
    aid=create_action(e,{'action_no':'V11-001','title':'Test','subtitle':None,'nature':'Formation','mode':'INTRA','client_name':'Client','client_type':'Professionnel','group_code':None,'planned_hours':3,'expected_participants':2,'admin_email':'a@b.fr','trainer_name':'Formateur','trainer_email':'f@b.fr','location':'Paris','notes':None,'source':'TEST'},'test')
    p1,_=add_participant(e,aid,{'last_name':'DUPONT','first_name':'Anne','birth_date':'1990-01-01'},'test')
    p2,_=add_participant(e,aid,{'last_name':'MARTIN','first_name':'Paul','birth_date':'1991-01-01'},'test')
    sid=add_slot(e,aid,'2026-09-02','09:00','12:00','test');return e,aid,p1,p2,sid

def test_absence_and_collective_catchup(tmp_path):
    e,aid,p1,p2,sid=seed(tmp_path);set_attendance_status(e,p1,sid,'ABSENT','malade','trainer');set_attendance_status(e,p2,sid,'ABSENT','malade','trainer')
    new=create_catchup_slot(e,sid,'2026-09-10','14:00','17:00',[p1,p2],'admin')
    s=one(e,'SELECT * FROM slots WHERE id=:s',{'s':new});assert s['parent_slot_id']==sid and s['slot_kind']=='RATTRAPAGE'

def test_evidence_locks_slot(tmp_path):
    e,aid,p1,p2,sid=seed(tmp_path);set_attendance_status(e,p1,sid,'ABSENT','absent','trainer')
    ok,msg=safe_update_slot(e,sid,{'slot_date':'2026-09-03','start_time':'10:00','end_time':'12:00','send_offset_min':-10,'reminder1_offset_min':20,'reminder2_offset_min':120,'close_offset_min':1440},'admin')
    assert not ok and 'preuve' in msg

def test_certificate_requires_evidence_and_countersignature(tmp_path):
    e,aid,p1,p2,sid=seed(tmp_path);ok,issues=can_issue_certificate(e,p1);assert not ok and issues
    countersign_slot(e,sid,'Formateur','f@b.fr','trainer','certifie');ok,issues=can_issue_certificate(e,p1);assert not ok

def test_report_preserves_original(tmp_path):
    from services import report_slot
    e,aid,p1,p2,sid=seed(tmp_path)
    ns=report_slot(e,sid,'2026-09-03','10:00','12:00','admin','accord commun')
    assert ns and ns != sid
    old=one(e,'SELECT * FROM slots WHERE id=:s',{'s':sid}); new=one(e,'SELECT * FROM slots WHERE id=:s',{'s':ns})
    assert old['status']=='REPORTE' and new['parent_slot_id']==sid and new['slot_kind']=='REPORT'

def test_pin_reset(tmp_path):
    from services import reset_participant_pin
    from security import verify_password
    e,aid,p1,p2,sid=seed(tmp_path); pin=reset_participant_pin(e,p1,'admin')
    assert len(pin)==4 and verify_password(pin,one(e,'SELECT pin_hash FROM participants WHERE id=:p',{'p':p1})['pin_hash'])

def test_catchup_resolves_absence_when_both_slots_countersigned(tmp_path):
    from db import execute, utcnow_iso
    from services import create_catchup_slot
    e,aid,p1,p2,sid=seed(tmp_path);set_attendance_status(e,p1,sid,'ABSENT','malade','trainer');countersign_slot(e,sid,'Formateur','f@b.fr','trainer','certifie')
    ns=create_catchup_slot(e,sid,'2026-09-02','09:00','12:00',[p1],'admin');countersign_slot(e,ns,'Formateur','f@b.fr','trainer','certifie')
    execute(e,"INSERT INTO signatures(participant_id,slot_id,signed_at,signature_path,signature_sha256,signer_name,method,status) VALUES(:p,:s,:at,'','x','P','EMAIL','VALIDE')",{'p':p1,'s':ns,'at':utcnow_iso()})
    ok,issues=can_issue_certificate(e,p1); assert ok,issues
