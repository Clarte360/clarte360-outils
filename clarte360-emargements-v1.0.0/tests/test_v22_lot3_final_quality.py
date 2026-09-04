from datetime import datetime, timezone, timedelta
from db import make_engine, init_db, one, execute
from services import *

def setup(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'x.db'));init_db(e);ensure_default_organization(e)
    aid=create_action(e,{'action_no':'CLA999','title':'Test final','subtitle':None,'nature':'FORMATION','mode':'INTRA','client_name':'Client','client_type':None,'group_code':None,'planned_hours':1,'expected_participants':1,'admin_email':'a@b.fr','trainer_name':'T','trainer_email':'t@b.fr','location':'Paris','notes':None,'source':'TEST'},'admin')
    execute(e,"UPDATE actions SET status='CLOTUREE' WHERE id=:a",{'a':aid})
    return e,aid

def test_client_contacts_and_recipients(tmp_path):
    e,a=setup(tmp_path);set_action_client_contacts(e,a,'adm@c.fr','form@c.fr','q@c.fr',None,'adm@c.fr','x')
    assert action_client_recipients(e,a,'FINAL')==['adm@c.fr','form@c.fr']
    assert action_client_recipients(e,a,'QUALITY')==['q@c.fr','adm@c.fr']

def test_final_bundle_schedule(tmp_path):
    e,a=setup(tmp_path);d=schedule_final_bundle(e,a,3); assert one(e,'select final_bundle_due_at from actions where id=:a',{'a':a})['final_bundle_due_at']==d

def test_management_summary_empty(tmp_path):
    e,a=setup(tmp_path);r=quality_management_summary(e);assert 'rubric_averages' in r and 'nps_score' in r

def test_new_schema_columns(tmp_path):
    e,a=setup(tmp_path);row=one(e,'select client_quality_email,final_bundle_due_at,portal_expires_at from actions where id=:a',{'a':a});assert row['client_quality_email'] is None

def test_final_transmission_configuration(tmp_path):
    e,a=setup(tmp_path);execute(e,"UPDATE actions SET client_quality_email='q@c.fr',client_training_email='f@c.fr' WHERE id=:a",{'a':a});configure_final_transmission(e,a,True,True,False,'A','B','x@c.fr','admin');assert configured_final_recipients(e,a)==['q@c.fr','x@c.fr']

def test_portal_retention_does_not_delete_internal_action(tmp_path):
    e,a=setup(tmp_path);bid=execute(e,"INSERT INTO beneficiaries(public_id,last_name,first_name,birth_date,current_email,active,created_at,updated_at) VALUES('B1','D','M','1990-01-01','m@x.fr',1,:n,:n)",{'n':utcnow_iso()});execute(e,"INSERT INTO beneficiary_portal_accounts(beneficiary_id,email,active,created_at,updated_at) VALUES(:b,'m@x.fr',1,:n,:n)",{'b':bid,'n':utcnow_iso()});purge_beneficiary_portal_documents(e,bid);assert one(e,'select id from actions where id=:a',{'a':a})
