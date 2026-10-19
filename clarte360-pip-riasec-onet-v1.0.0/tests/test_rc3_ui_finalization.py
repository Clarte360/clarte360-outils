import copy
import json
import ast
from pathlib import Path
import pytest
from clarte360_pip.domain import RunMode
from clarte360_pip.framework import public_access as pa,server_store as store
from clarte360_pip.framework.persistence import build_snapshot,restore_snapshot,infer_resume_page
from clarte360_pip import delivery
from rc3_support import make_state,isolate,verify_identity,ui_namespace,Rerun,events,State


def test_feeling_accepted_with_aucune_and_saved_before_rerun(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state();s.feeling={}
    values={f'feel_{k}':4 for k in ('global','dominants','nuances','useful')}
    ns,ui=ui_namespace(s,pressed=['Valider mon ressenti'],values=values)
    with pytest.raises(Rerun):ns['render_feeling']()
    assert s.feeling['answers']['over']=='Aucune' and s.feeling['answers']['under']=='Aucune'
    snap=store.load_latest_accompanied_snapshot('TEST-A','TEST-B','TEST-PRES')
    assert snap['feeling'] and snap['navigation_page']=='finished'
    assert not any(kw.get('mime')=='application/pdf' for _,kw in ui.downloads)
    assert not events(tmp_path)

@pytest.mark.parametrize('missing',['global','dominants','nuances','useful'])
def test_each_missing_feedback_is_explicit_and_does_not_finalize(monkeypatch,tmp_path,missing):
    isolate(monkeypatch,tmp_path);s=make_state();s.feeling={}
    values={f'feel_{k}':4 for k in ('global','dominants','nuances','useful')};values[f'feel_{missing}']=None
    ns,ui=ui_namespace(s,pressed=['Valider mon ressenti'],values=values);ns['render_feeling']()
    assert not s.feeling
    from clarte360_pip.feeling import QUESTIONS
    assert any(x[0]=='warning' and QUESTIONS[missing]['text'] in x[1][0] for x in ui.calls)
    assert not events(tmp_path)


def test_public_callback_choice_required_no_effect_on_scores(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s);before=copy.deepcopy(s.pip_scoring);s.feeling={}
    values={f'feel_{k}':4 for k in ('global','dominants','nuances','useful')}
    ns,ui=ui_namespace(s,pressed=['Valider mon ressenti'],values=values);ns['render_feeling']()
    assert not s.feeling and s.pip_scoring==before
    values['public_callback_choice']='NON'
    with pytest.raises(Rerun):ns['render_feeling']()
    assert s.feeling and s.pip_scoring==before


def test_public_mail_failure_leaves_pdf_and_pseudonymized_study(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s);ns,ui=ui_namespace(s,real_pdf=True)
    calls=[]
    ns['send_email']=lambda *a,**k:(calls.append(1) or False,'Unavailable in test')
    ns['render_finished']();ns['render_finished']()
    assert len(calls)==1
    assert any(kw.get('mime')=='application/pdf' and kw['data'].startswith(b'%PDF-') for _,kw in ui.downloads)
    files=list((tmp_path/'public'/'study').glob('*.json')); assert len(files)==1
    study=json.loads(files[0].read_text());assert study['status']=='TERMINE'
    raw=json.dumps(study)
    assert s.public_identity['email'] not in raw and s.passation_id not in raw and s.public_participant_id not in raw
    assert not events(tmp_path)
    assert not (tmp_path/'reports').exists()  # no extra nominative PUBLIC PDF store


def test_public_study_id_not_duplicated_after_snapshot_resume(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s);ns,_=ui_namespace(s);ns['render_finished']()
    before=s.public_study_id
    restored=State(launch_context=s.launch_context);restore_snapshot(build_snapshot(s),restored)
    ns2,_=ui_namespace(restored);ns2['render_finished']()
    assert restored.public_study_id==before and len(list((tmp_path/'public'/'study').glob('*.json')))==1


def test_failed_study_storage_does_not_hide_pdf(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s);ns,ui=ui_namespace(s)
    ns['save_public_study_record']=lambda *a:(_ for _ in ()).throw(PermissionError('secret'))
    ns['render_finished']()
    assert any(kw.get('mime')=='application/pdf' for _,kw in ui.downloads)
    assert any(x[0]=='warning' for x in ui.calls)


def test_failed_report_keeps_feedback_and_emits_nothing(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state();s.navigation_page='finished'
    store.save_accompanied_snapshot(s,'TEST-A','TEST-B','TEST-PRES')
    ns,ui=ui_namespace(s);ns['build_pip_report_pdf']=lambda *a:(_ for _ in ()).throw(RuntimeError('SECRET detail'))
    ns['render_finished']()
    assert s.feeling and not events(tmp_path)
    assert store.load_latest_accompanied_snapshot('TEST-A','TEST-B','TEST-PRES')['feeling']
    assert 'SECRET' not in str(ui.calls)


def test_initial_combined_keeps_pip_results_masked_before_onet(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(journey='PIP_PUIS_ONET60',onet=False)
    ns,ui=ui_namespace(s);ns['render_finished']()
    assert not ui.downloads and not events(tmp_path)
    assert not ns['_finalization_requirements_met'](s)
    from clarte360_pip.journey import results_allowed
    assert not results_allowed(s.journey,True,False)


def test_callback_outbox_contains_no_scores_or_reports(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s);s.feeling={}
    values={f'feel_{k}':4 for k in ('global','dominants','nuances','useful')};values['public_callback_choice']='OUI'
    ns,ui=ui_namespace(s,pressed=['Valider mon ressenti'],values=values)
    with pytest.raises(Rerun):ns['render_feeling']()
    ns['render_finished']()
    es=events(tmp_path);assert len(es)==1 and es[0]['event_type']=='CALLBACK_REQUESTED'
    assert not {'scores','answers','documents','passation_id','study_id'}.intersection(es[0]['payload'])
    ns['render_finished']();assert len(events(tmp_path))==1


def test_onet_in_progress_resume_not_hidden_by_previous_final_pip():
    s=make_state();s.completed_at='2026-10-18T00:00:00+00:00';s.journey='PIP_PUIS_ONET60'
    s.onet_state={'questions':[{'index':1,'text':'Fixture'}],'completed':False}
    assert infer_resume_page(s)=='onet_questionnaire'


def test_pseudonymized_study_path_cannot_escape(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);s.public_study_id='../outside'
    with pytest.raises(ValueError):pa.save_public_study_record(s)
    assert not (tmp_path/'outside.json').exists()
