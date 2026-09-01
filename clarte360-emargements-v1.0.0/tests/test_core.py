from pathlib import Path
import tempfile
from db import make_engine,init_db,one
from services import create_action,add_participant,add_slot,slot_duration_hours,action_progress,export_action_json

def engine_tmp():
    p=tempfile.NamedTemporaryFile(suffix='.db',delete=False);p.close();e=make_engine('sqlite:///'+p.name);init_db(e);return e

def test_action_participant_slot():
    e=engine_tmp();aid=create_action(e,{'action_no':'CLA9999','title':'Test','subtitle':None,'nature':'Formation','mode':'INTRA','client_name':None,'client_type':'Non précisé','group_code':None,'planned_hours':7.0,'expected_participants':1,'admin_email':'a@b.c','trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'},'test')
    pid,pin=add_participant(e,aid,{'individual_action_no':'CLA9999','last_name':'DURAND','birth_name':None,'first_name':'Marie','birth_date':None,'email':'m@example.com','employee_id':None,'company_name':None,'phone':None},'test')
    sid=add_slot(e,aid,'2026-09-01','08:00','11:30','test');assert len(pin)==4
    s=one(e,'SELECT * FROM slots WHERE id=:id',{'id':sid});assert slot_duration_hours(s)==3.5
    p=action_progress(e,aid);assert p['expected']==1 and p['signed']==0
    assert b'CLA9999' in export_action_json(e,aid)
