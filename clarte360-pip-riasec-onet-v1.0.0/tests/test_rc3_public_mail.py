import copy
import json
import logging
import smtplib
from datetime import datetime,timezone,timedelta
import pytest
from clarte360_pip.domain import RunMode
from clarte360_pip import delivery
from clarte360_pip.framework import public_access as pa, smtp
from clarte360_pip.framework.config import SmtpSettings
from clarte360_pip.framework.persistence import build_snapshot,restore_snapshot
from rc3_support import isolate,make_state,verify_identity,add_onet,State

SETTINGS=SmtpSettings('smtp.invalid',465,'fake-user','fake-password','from@example.test',None)
PIP=(delivery.PIP_NAME,b'%PDF-1.4\nPIP','application/pdf')
ONET=(delivery.ONET_NAME,b'%PDF-1.4\nONET','application/pdf')


def test_success_is_not_repeated_after_refresh_or_old_json(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s)
    old=build_snapshot(s);sent=[]
    sender=lambda *a,**kw:(sent.append(kw) or True,'Accepted')
    assert delivery.public_report_mail(s,[PIP],SETTINGS,sender)['status']=='SENT'
    assert delivery.public_report_mail(s,[PIP],SETTINGS,sender)['sent_now']==[]
    restored=State(launch_context=s.launch_context);restore_snapshot(old,restored)
    delivery.public_report_mail(restored,[PIP],SETTINGS,sender)
    assert len(sent)==1 and sent[0]['to_email']=='alice@example.test'


def test_failed_smtp_is_not_retried_until_explicit_click_and_delay(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s);sent=[]
    t=datetime(2026,10,18,tzinfo=timezone.utc)
    sender=lambda *a,**kw:(sent.append(kw) or False,'Refused in test')
    delivery.public_report_mail(s,[PIP],SETTINGS,sender,now=t)
    delivery.public_report_mail(s,[PIP],SETTINGS,sender,now=t+timedelta(seconds=65))
    assert len(sent)==1
    delivery.public_report_mail(s,[PIP],SETTINGS,sender,retry=True,now=t+timedelta(seconds=30))
    assert len(sent)==1
    for seconds in (65,130,195,260):
        delivery.public_report_mail(s,[PIP],SETTINGS,sender,retry=True,now=t+timedelta(seconds=seconds))
    assert len(sent)==3  # bounded manual retries


def test_new_onet_is_sent_without_resending_the_pip(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s);sent=[]
    sender=lambda *a,**kw:(sent.append([x[0] for x in kw['attachments']]) or True,'Accepted')
    delivery.public_report_mail(s,[PIP],SETTINGS,sender)
    add_onet(s);delivery.public_report_mail(s,[PIP,ONET],SETTINGS,sender)
    delivery.public_report_mail(s,[PIP,ONET],SETTINGS,sender)
    assert sent==[[delivery.PIP_NAME],[delivery.ONET_NAME]]


def test_unverified_import_retains_71_answers_but_cannot_send(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s)
    s.pip_state['answers'].pop(s.pip_state['order'][-1]);s.pip_state['completed']=False;s.pip_scoring={};s.feeling={};s.completed_at=None
    snap=build_snapshot(s);snap['public_identity']['email']='different@example.test'
    out=State(launch_context=s.launch_context)
    pa.restore_public_upload(snap,out)
    assert not out.public_access_verified and out.navigation_page=='accueil'
    assert len(out.pip_state['answers'])==71 and out.public_verification_return_page=='pip_questionnaire'
    result=delivery.public_report_mail(out,[PIP],SETTINGS,lambda *a,**k:pytest.fail('Unverified e-mail must never be used'))
    assert result['status']=='VERIFY'


def test_same_verified_recipient_can_resume_import(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s)
    out=State(launch_context=s.launch_context)
    pa.restore_public_upload(build_snapshot(s),out)
    assert out.public_access_verified and pa.verified_public_email(out)=='alice@example.test'


def test_untrusted_boolean_without_server_proof_is_rejected(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC)
    assert pa.verified_public_email(s) is None
    pa.enforce_public_verification(s)
    assert not s.public_access_verified and s.pip_state['answers']


def test_accompanied_json_cannot_be_imported_as_public(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);ac=make_state();pub=make_state(RunMode.PUBLIC)
    before=copy.deepcopy(pub)
    with pytest.raises(ValueError):pa.restore_public_upload(build_snapshot(ac),pub)
    assert pub==before


def test_access_code_bound_to_issued_email(monkeypatch):
    monkeypatch.setattr(pa,'send_email',lambda *a,**k:(True,'ok'))
    monkeypatch.setattr(pa,'generate_access_code',lambda:'123456')
    identity=make_state(RunMode.PUBLIC).public_identity
    ok,_,state=pa.issue_public_code(identity,SETTINGS)
    assert ok
    assert not pa.verify_public_code('123456',state,expected_email='other@example.test')
    assert pa.verify_public_code('123456',state,expected_email='alice@example.test')

@pytest.mark.parametrize('exc,category',[
 (smtplib.SMTPAuthenticationError(535,b'private-password'),'AUTH'),
 (smtplib.SMTPRecipientsRefused({'secret@example.test':(550,b'private-email')}),'RECIPIENT'),
 (smtplib.SMTPDataError(552,b'private-report'),'CONTENT'),
 (smtplib.SMTPSenderRefused(550,b'private-message','secret@example.test'),'SENDER'),
 (TimeoutError('private-server'),'CONNECTION'),
])
def test_smtp_categories_logged_without_private_details(monkeypatch,caplog,exc,category):
    class BadSMTP:
        def __init__(self,*a,**kw):raise exc
    monkeypatch.setattr(smtp.smtplib,'SMTP_SSL',BadSMTP)
    with caplog.at_level(logging.WARNING):ok,message=smtp.send_email(SETTINGS,'Test','Body','alice@example.test',[PIP])
    assert not ok and category in caplog.text
    assert 'private-' not in caplog.text+message and 'secret@example' not in caplog.text+message
    assert SETTINGS.password not in caplog.text+message


def test_crash_after_smtp_attempt_does_not_cause_automatic_resend(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s);calls=[]
    def interrupted(*a,**k):calls.append(1);raise RuntimeError('network result unknown')
    with pytest.raises(RuntimeError):delivery.public_report_mail(s,[PIP],SETTINGS,interrupted)
    delivery.public_report_mail(s,[PIP],SETTINGS,interrupted)
    assert len(calls)==1


def test_email_receipt_contains_no_report_content_or_plain_email(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s)
    delivery.public_report_mail(s,[PIP],SETTINGS,lambda *a,**k:(True,'Accepted'))
    path=next((tmp_path/'public'/'report_delivery').rglob('*.json'));raw=path.read_text()
    assert '%PDF' not in raw and 'alice@example.test' not in raw and 'pip_answers' not in raw
