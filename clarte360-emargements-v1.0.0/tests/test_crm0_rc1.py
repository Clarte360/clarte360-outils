import json
from db import make_engine, init_db, one, q
from services import (process_pip_public_event, add_crm_note, create_crm_task, set_crm_task_status,
                      create_crm_contact, create_action, link_crm_contact_action, list_crm_action_links)


def eng(tmp_path):
    e=make_engine(f"sqlite:///{tmp_path/'crm0.db'}"); init_db(e); return e


def test_pip_marketing_opt_in_and_interest_mapping(tmp_path):
    e=eng(tmp_path)
    event={'event_type':'CONTACT_EMAIL_VERIFIED','event_id':'evt1','payload':{
      'first_name':'Dom','last_name':'Test','email':'dom@example.com','phone':'0102030405','company':'ACME',
      'marketing_opt_in':True,'rgpd_text_version':'RGPD-X','interests':['Solutions collectives pour mon entreprise'],
      'email_verified_at':'2026-09-19T10:00:00+00:00'}}
    process_pip_public_event(e,event)
    c=one(e,"SELECT * FROM crm_contacts WHERE email='dom@example.com'")
    assert c['marketing_consent']==1
    assert c['rgpd_notice_version']=='RGPD-X'
    ints=json.loads(c['interests_json'])
    assert 'PIP-RIASEC' in ints
    assert 'Solutions collectives pour mon entreprise' in ints


def test_crm_note_task_and_action_link(tmp_path):
    e=eng(tmp_path)
    c=create_crm_contact(e,'Dom','Test','dom@example.com',company='ACME')
    add_crm_note(e,c['id'],'Appel effectué, proposition à envoyer','admin')
    t=create_crm_task(e,c['id'],'Envoyer proposition',due_at='2026-09-25',actor='admin')
    set_crm_task_status(e,t['id'],'FAIT','admin')
    aid=create_action(e,{'action_no':'CLA9999','title':'Essai CRM','subtitle':None,'nature':'Formation','mode':'INTRA','delivery_mode':'PRESENTIEL',
      'client_name':'ACME','client_type':'Professionnel','group_code':None,'planned_hours':7,'expected_participants':1,'admin_email':'a@b.fr',
      'trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'},'admin')
    link_crm_contact_action(e,c['id'],aid,'CLIENT','admin')
    links=list_crm_action_links(e,c['id'])
    assert len(links)==1 and links[0]['action_no']=='CLA9999'
    c2=one(e,'SELECT * FROM crm_contacts WHERE id=:i',{'i':c['id']})
    assert c2['status']=='CLIENT'
    ev=[x['event_type'] for x in q(e,'SELECT * FROM crm_events WHERE contact_id=:c',{'c':c['id']})]
    assert 'NOTE' in ev and 'TASK_CREATED' in ev and 'ACTION_LINKED' in ev
