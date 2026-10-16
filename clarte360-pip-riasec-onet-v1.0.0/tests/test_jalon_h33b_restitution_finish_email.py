from pathlib import Path
from unittest.mock import patch
from clarte360_pip.framework.persistence import build_snapshot, restore_snapshot
from clarte360_pip.framework.public_access import save_public_study_record
from clarte360_pip.framework.smtp import send_email
from clarte360_pip.framework.config import SmtpSettings

ROOT=Path(__file__).resolve().parents[1]
PAGES=(ROOT/'clarte360_pip/ui/pages.py').read_text()

def test_restitution_is_screen_gate_not_pdf_view_gate():
    assert 'Vous n’avez pas besoin d’ouvrir ni de consulter le PDF' in PAGES
    assert 'restitution_ok and st.button("J’ai consulté mes résultats — donner mon ressenti"' in PAGES
    assert 'if not bool(st.session_state.get("restitution_presented"))' in PAGES

def test_snapshot_persists_h33b_finish_and_email_flags():
    s={'passation_id':'abc-123','pip_state':{},'restitution_presented':True,'final_report_email_sent':True,'final_report_email_sent_at':'2026-09-24T10:00:00+00:00'}
    snap=build_snapshot(s)
    assert snap['restitution_presented'] is True and snap['final_report_email_sent'] is True

def test_restore_cannot_bypass_restitution_to_feeling():
    payload={'schema':'clarte360.pip.run.v1','passation_id':'abc-123','journey':'PIP_SEUL','navigation_page':'feeling','pip_state':{'answers':{},'index':0,'completed':True},'onet_state':{},'restitution_presented':False}
    out={}
    restore_snapshot(payload,out)
    assert out['navigation_page']=='pip_results_gate'

def test_study_record_before_feeling_is_not_termine(tmp_path):
    import clarte360_pip.framework.public_access as pa
    state={'study_consent':True,'public_study_id':'study-test-1','journey':'PIP_SEUL','pip_state':{'answers':{'q1':1}},'pip_scoring':{'complete':True},'onet_state':{},'restitution_presented':True}
    with patch.object(pa,'STUDY_DIR',tmp_path):
        path=save_public_study_record(state)
    import json
    data=json.loads(path.read_text())
    assert data['status']=='EN_COURS' and data['completed_at'] is None

def test_study_record_after_feeling_is_termine(tmp_path):
    import clarte360_pip.framework.public_access as pa
    state={'study_consent':True,'public_study_id':'study-test-2','journey':'PIP_SEUL','pip_state':{'answers':{'q1':1}},'pip_scoring':{'complete':True},'onet_state':{},'restitution_presented':True,'feeling':{'answers':{'global':4}},'completed_at':'2026-09-24T10:00:00+00:00'}
    with patch.object(pa,'STUDY_DIR',tmp_path):
        path=save_public_study_record(state)
    import json
    data=json.loads(path.read_text())
    assert data['status']=='TERMINE' and data['completed_at']==state['completed_at']

def test_smtp_supports_pdf_attachments():
    settings=SmtpSettings(server='smtp.example.test',port=465,username='u',password='p',from_email='from@example.test',to_email='to@example.test')
    sent={}
    class Dummy:
        def __init__(self,*a,**k): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def login(self,*a): pass
        def send_message(self,msg): sent['msg']=msg
    with patch('clarte360_pip.framework.smtp.smtplib.SMTP_SSL',Dummy):
        ok,_=send_email(settings,'Sujet','Corps',attachments=[('rapport.pdf',b'%PDF-test','application/pdf')])
    assert ok and any(p.get_filename()=='rapport.pdf' for p in sent['msg'].iter_attachments())
