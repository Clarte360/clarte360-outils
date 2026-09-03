from db import make_engine, init_db, one, execute
from services import create_action, add_participant, add_slot, activate_action, ensure_tokens_and_events
from mailer import resolve_mail_config


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e


def base_action(e):
    return create_action(e,{
        'action_no':'T21','title':'Test V2.1','subtitle':None,'nature':'Formation','mode':'INDIVIDUEL',
        'client_name':None,'client_type':'Non précisé','group_code':None,'planned_hours':1.5,
        'expected_participants':1,'admin_email':'a@b.fr','trainer_name':None,'trainer_email':None,
        'location':'Teams','notes':None,'source':'TEST'
    },'test')


def test_mail_prefers_uppercase_mail_and_normalizes_aliases():
    cfg=resolve_mail_config({'MAIL':{'SMTP_SERVER':'mail.example.fr','SMTP_PORT':587,'USER':'u','PASSWORD':'p','SENDER_EMAIL':'x@example.fr','USE_TLS':True}})
    assert cfg['_source']=='MAIL'
    assert cfg['host']=='mail.example.fr'
    assert cfg['port']==587
    assert cfg['username']=='u'
    assert cfg['from_email']=='x@example.fr'
    assert cfg['security']=='starttls'
    assert cfg['enabled'] is True


def test_activation_rejects_missing_participant_email_when_attendance_enabled():
    e=eng(); aid=base_action(e)
    add_participant(e,aid,{'last_name':'DURAND','first_name':'Marie','email':None},'test')
    add_slot(e,aid,'2026-09-04','09:00','10:30','test',send=-90)
    ok,issues=activate_action(e,aid,'test')
    assert not ok
    assert any('Email manquant' in x for x in issues)
    assert one(e,'SELECT status FROM actions WHERE id=:a',{'a':aid})['status']=='BROUILLON'


def test_activation_sets_active_but_action_remains_editable():
    e=eng(); aid=base_action(e)
    add_participant(e,aid,{'last_name':'DURAND','first_name':'Marie','email':'m@example.fr'},'test')
    add_slot(e,aid,'2026-09-04','09:00','10:30','test',send=-90)
    ok,issues=activate_action(e,aid,'test')
    assert ok and not issues
    assert one(e,'SELECT status FROM actions WHERE id=:a',{'a':aid})['status']=='ACTIVE'
    execute(e,"UPDATE actions SET title='Modifié' WHERE id=:a",{'a':aid})
    assert one(e,'SELECT title FROM actions WHERE id=:a',{'a':aid})['title']=='Modifié'


def test_recalculating_pending_event_clears_old_last_error():
    e=eng(); aid=base_action(e)
    pid,_=add_participant(e,aid,{'last_name':'DURAND','first_name':'Marie','email':'m@example.fr'},'test')
    sid=add_slot(e,aid,'2026-09-04','09:00','10:30','test',send=-90)
    ensure_tokens_and_events(e,aid,'https://example.fr','Europe/Paris')
    execute(e,"UPDATE email_events SET last_error='535 old auth error' WHERE participant_id=:p AND slot_id=:s",{'p':pid,'s':sid})
    ensure_tokens_and_events(e,aid,'https://example.fr','Europe/Paris')
    assert one(e,'SELECT last_error FROM email_events WHERE participant_id=:p AND slot_id=:s AND event_type="INITIAL"',{'p':pid,'s':sid})['last_error'] is None
