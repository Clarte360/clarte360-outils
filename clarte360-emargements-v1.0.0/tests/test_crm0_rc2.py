import json
from db import make_engine, init_db, one, q
from services import (
    create_crm_contact, add_crm_note, create_crm_task, update_crm_task, delete_crm_task,
    create_action, link_crm_contact_action, unlink_crm_contact_action, purge_crm_contact,
    list_crm_action_links, delete_crm_note
)


def eng(tmp_path):
    e=make_engine(f"sqlite:///{tmp_path/'crm0rc2.db'}"); init_db(e); return e


def mk_action(e,no='CLA-RC2'):
    return create_action(e,{'action_no':no,'title':'Action CRM RC2','subtitle':None,'nature':'Formation','mode':'INTRA','delivery_mode':'PRESENTIEL',
      'client_name':'ACME','client_type':'Professionnel','group_code':None,'planned_hours':7,'expected_participants':1,'admin_email':'a@b.fr',
      'trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'},'admin')


def test_note_task_and_unlink_are_administrable(tmp_path):
    e=eng(tmp_path)
    c=create_crm_contact(e,'Dom','Test','dom@example.com',company='ACME')
    note_id=add_crm_note(e,c['id'],'Première note','admin')
    delete_crm_note(e,c['id'],note_id,'admin')
    assert one(e,"SELECT id FROM crm_events WHERE id=:i AND event_type='NOTE'",{'i':note_id}) is None
    assert one(e,"SELECT id FROM crm_events WHERE contact_id=:c AND event_type='NOTE_DELETED'",{'c':c['id']})

    t=create_crm_task(e,c['id'],'Appeler',due_at='2026-09-25',notes='Avant midi',actor='admin')
    update_crm_task(e,t['id'],title='Rappeler',due_at='2026-09-26',notes='Après 14h',status='FAIT',actor='admin')
    t2=one(e,'SELECT * FROM crm_tasks WHERE id=:i',{'i':t['id']})
    assert t2['title']=='Rappeler' and t2['status']=='FAIT' and t2['due_at']=='2026-09-26'
    delete_crm_task(e,t['id'],'admin')
    assert one(e,'SELECT id FROM crm_tasks WHERE id=:i',{'i':t['id']}) is None

    aid=mk_action(e)
    link_crm_contact_action(e,c['id'],aid,'CLIENT','admin')
    assert len(list_crm_action_links(e,c['id']))==1
    unlink_crm_contact_action(e,c['id'],aid,'admin')
    assert list_crm_action_links(e,c['id'])==[]
    assert one(e,'SELECT id FROM actions WHERE id=:i',{'i':aid}) is not None


def test_purge_crm_contact_deletes_only_crm_content(tmp_path):
    e=eng(tmp_path)
    c=create_crm_contact(e,'Eva','Test','eva@example.com',company='ACME')
    add_crm_note(e,c['id'],'Note à supprimer','admin')
    create_crm_task(e,c['id'],'Tâche à supprimer',actor='admin')
    aid=mk_action(e,'CLA-RC2-B')
    link_crm_contact_action(e,c['id'],aid,'CLIENT','admin')
    ok,msg=purge_crm_contact(e,c['id'],'admin')
    assert ok and msg==''
    assert one(e,'SELECT id FROM crm_contacts WHERE id=:i',{'i':c['id']}) is None
    assert q(e,'SELECT * FROM crm_events WHERE contact_id=:c',{'c':c['id']})==[]
    assert q(e,'SELECT * FROM crm_tasks WHERE contact_id=:c',{'c':c['id']})==[]
    assert q(e,'SELECT * FROM crm_action_links WHERE contact_id=:c',{'c':c['id']})==[]
    # The linked business action must remain intact.
    assert one(e,'SELECT id FROM actions WHERE id=:i',{'i':aid}) is not None
