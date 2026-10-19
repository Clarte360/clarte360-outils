"""Local synthetic fixtures. No VPS, SMTP server or O*NET API is contacted."""
from __future__ import annotations
import ast
import json
import logging
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
from uuid import uuid4

from clarte360_pip.domain import LaunchContext, RunMode
from clarte360_pip.pip_data.loader import load_pip_bank
from clarte360_pip.questionnaire import build_order, QuestionnaireEngine
from clarte360_pip.scoring import score_pip
from clarte360_pip.feeling import QUESTIONS, build_feeling_record
from clarte360_pip.framework import server_store as store, public_access as pa
from clarte360_pip.connectors import gestion_actions as ga
from clarte360_pip import delivery
from clarte360_pip.framework.config import ASSETS_DIR, RGPD_TEXT_VERSION, load_smtp_settings, load_onet_settings, SmtpSettings
from clarte360_pip.framework.persistence import snapshot_bytes, restore_snapshot, infer_resume_page
from clarte360_pip.framework.unsaved_guard import mark_public_work_saved
from clarte360_pip.reporting import build_pip_report_pdf, build_onet_report_pdf, PIP_REPORT_VERSION, ONET_REPORT_VERSION
from clarte360_pip.journey import next_after_pip, results_allowed
from clarte360_pip.pip_data.validation import assert_valid_bank
from clarte360_pip.version import APP_VERSION
from clarte360_pip.connectors.onet import OnetPort, OnetApiError, normalize_onet_results, ONET_INSTRUMENT, ONET_API_VERSION, ONET_LANGUAGE

class State(dict):
    def __getattr__(self, k):
        try: return self[k]
        except KeyError as exc: raise AttributeError(k) from exc
    def __setattr__(self, k, v): self[k] = v

class Rerun(BaseException): pass

class UI:
    def __init__(self,state,pressed=(),values=None):
        self.session_state = state
        self.pressed = set(pressed)
        self.values = values or {}
        self.calls = []
        self.downloads = []
        self.secrets = {}
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def rerun(self): raise Rerun()
    def stop(self): raise Rerun()
    def button(self,label,**kwargs):
        self.calls.append(('button',label,kwargs))
        return not kwargs.get('disabled') and (label in self.pressed or kwargs.get('key') in self.pressed)
    def radio(self,label,options,**kwargs):
        key=kwargs.get('key',label)
        if key in self.values: return self.values[key]
        i=kwargs.get('index',0)
        return options[i] if i is not None else None
    def selectbox(self,label,options,**kwargs): return self.values.get(kwargs.get('key',label),options[0])
    def expander(self,*a,**kw): return self
    def columns(self,n): return [self]*n
    def download_button(self,label,**kwargs):
        self.downloads.append((label,kwargs)); return False
    def __getattr__(self,name):
        def call(*args,**kwargs): self.calls.append((name,args,kwargs))
        return call


def isolate(monkeypatch,tmp_path):
    for module in (ga, store, delivery): monkeypatch.setattr(module,'PERSISTENT_DATA_DIR',tmp_path)
    monkeypatch.setattr(pa,'PUBLIC_DIR',tmp_path/'public')
    monkeypatch.setattr(pa,'LEADS_DIR',tmp_path/'public'/'leads')
    monkeypatch.setattr(pa,'STUDY_DIR',tmp_path/'public'/'study')
    return tmp_path


def make_state(mode=RunMode.ACCOMPANIMENT, run='TEST-RUN', prescription='TEST-PRES', journey='PIP_SEUL', onet=False):
    bank=load_pip_bank(); order=build_order(bank,run)
    answers={q: i%5+1 for i,q in enumerate(order)}
    s=State(passation_id=run,session_id='SESSION-'+run, journey=journey,
            pip_state={'bank_version':bank['bank_version'],'order':order,'answers':answers,'index':71,'completed':True},
            pip_scoring=asdict(score_pip(bank,answers)), onet_state={},
            restitution_presented=True, feeling=build_feeling_record({'global':4,'dominants':3,'nuances':4,'useful':5,'over':'Aucune','under':'Aucune'},journey,run_mode=mode.value),
            completed_at=None,navigation_page='finished',last_useful_page='finished',report_documents=[],
            final_event_published=False,delivery_state={},study_consent=True,
            public_identity={},public_access_verified=False,
            rgpd_acceptance={'consentement':True,'version_texte':RGPD_TEXT_VERSION,'study_consent':True},
            access_history=[],session_history=[])
    if mode is RunMode.PUBLIC:
        s.launch_context=LaunchContext(mode=mode)
        s.public_participant_id='PUBLIC-'+run
        s.public_identity={'first_name':'Alice','last_name':'Exemple','phone':'+33123456789','email':'alice@example.test','job_title':'','company':''}
        s.public_access_verified=True
        s.public_email_verified_at='2026-01-01T00:00:00+00:00'
    else:
        s.launch_context=LaunchContext(mode=mode,action_id='TEST-A',beneficiary_id='TEST-B',participant_id='TEST-P',prescription_id=prescription,
                                      beneficiary_first_name='Alice',beneficiary_last_name='Exemple',action_number='TEST',action_title='Recette fictive',rights=('PIP_RUN','PIP_RESUME','PIP_RESULT_READ','PIP_STATUS'))
    if journey!='PIP_SEUL': s.onet_selected_timing='PRE_PIP'
    if onet: add_onet(s)
    return s


def add_onet(s):
    s.onet_state={'completed':True,'answers':{str(i):i%5+1 for i in range(1,61)},'index':59,
                  'results':[{'code':k,'title':k.title(),'score':30-i*4} for i,k in enumerate(['realistic','investigative','artistic','social','enterprising','conventional'])],
                  'selected_timing':s.get('onet_selected_timing','POST_PIP_RESULTS'),
                  'instrument':ONET_INSTRUMENT,'api_version':ONET_API_VERSION,'language':'en'}
    s.journey='PIP_PUIS_ONET60'


def verify_identity(s):
    return pa.save_public_lead(s.public_participant_id,s.public_identity,False,True)


def ui_namespace(s,pressed=(),values=None,real_pdf=False):
    ui=UI(s,pressed,values)
    ns={k:v for k,v in globals().items() if not k.startswith('__')}
    ns.update(st=ui,LOG=logging.getLogger('rc3_test'),
              accompanied_report=delivery.accompanied_report,
              publish_accompanied_reports=delivery.publish_accompanied_reports,
              public_report_mail=delivery.public_report_mail,
              PIP_NAME=delivery.PIP_NAME,ONET_NAME=delivery.ONET_NAME,
              verified_public_email=pa.verified_public_email,
              save_public_study_record=pa.save_public_study_record,
              save_accompanied_snapshot=store.save_accompanied_snapshot,
              GestionActionsPort=ga.GestionActionsPort,
              send_email=lambda *a,**kw:(True,'Accepted by test transport'),
              pdf_pages_as_png=lambda *a:[],
              _render_pip_report_preview_before_feeling=lambda:True)
    names={'_utcnow','_public_contact_payload','_accompanied_final_payload','_save_if_accompanied',
           '_publish_if_accompanied','render_feeling','_finalization_requirements_met','_final_pdf',
           '_render_public_mail','render_finished','render_pip_intro','render_pip_questionnaire',
           'render_combined_results','render_onet_intro','render_onet_questionnaire','_onet_port'}
    module=ast.parse((Path(__file__).parents[1]/'clarte360_pip/ui/pages.py').read_text())
    ns['DIMENSION_LABELS']=ast.literal_eval(next(n.value for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DIMENSION_LABELS' for t in n.targets)))
    body=[n for n in module.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
    exec(compile(ast.Module(body=body,type_ignores=[]),'<PIP UI functions>','exec'),ns)
    if not real_pdf:
        ns['build_pip_report_pdf']=lambda *a: b'%PDF-1.4\nPIP fictional report\n%%EOF'
        ns['build_onet_report_pdf']=lambda *a: b'%PDF-1.4\nONET fictional report\n%%EOF'
    return ns,ui


def events(root):
    p=root/'connector_outbox'/'gestion_actions'/'events.jsonl'
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []
