"""Actual UI functions with an in-memory UI adapter; not a browser test."""
import copy
import pytest
from types import SimpleNamespace
from clarte360_pip.domain import RunMode
from clarte360_pip.framework.persistence import build_snapshot, restore_snapshot
from clarte360_pip.framework import server_store as store
from rc3_support import make_state, isolate, ui_namespace, Rerun, State, events, verify_identity

@pytest.mark.parametrize('journey,next_page',[('PIP_SEUL','pip_results_gate'),('PIP_PUIS_ONET60','onet_pending')])
def test_last_pip_answer_saves_actual_scoring_without_premature_final_event(monkeypatch,tmp_path,journey,next_page):
    isolate(monkeypatch,tmp_path)
    s=make_state(journey=journey);q=s.pip_state['order'][-1]
    s.pip_state['answers'].pop(q);s.pip_state.pop('completed');s.pip_scoring={};s.feeling={};s.restitution_presented=False
    s.navigation_page=s.last_useful_page='pip_questionnaire'
    ns,ui=ui_namespace(s,pressed=['Terminer la passation'],values={'ans_'+q:4})
    with pytest.raises(Rerun):ns['render_pip_questionnaire']()
    assert s.pip_state['completed'] and len(s.pip_state['answers'])==72 and s.pip_scoring['complete']
    assert s.navigation_page==next_page
    saved=store.load_latest_accompanied_snapshot('TEST-A','TEST-B','TEST-PRES')
    assert len(saved['pip_state']['answers'])==72
    assert not any(e['event_type']=='TERMINE' for e in events(tmp_path))

@pytest.mark.parametrize('after_first_finalization',[False,True])
def test_last_onet_answer_uses_existing_pipeline_then_finalizes(monkeypatch,tmp_path,after_first_finalization):
    isolate(monkeypatch,tmp_path);s=make_state()
    ns,ui=ui_namespace(s)
    if after_first_finalization:ns['render_finished']()
    else:s.feeling={};s.restitution_presented=False
    s.journey='PIP_PUIS_ONET60';s.onet_selected_timing='POST_PIP_RESULTS' if after_first_finalization else 'PRE_PIP'
    s.onet_state={'questions':[{'index':i,'text':'Synthetic routing fixture'} for i in range(1,61)],
                  'answers':{str(i):4 for i in range(1,60)},'index':59,'completed':False}
    s.navigation_page='onet_questionnaire'
    ns,ui=ui_namespace(s,pressed=['Finish O*NET'],values={'onet_60':4})
    calls=[]
    def score(answers):
        calls.append(copy.deepcopy(answers))
        return {'result':[{'area':'Realistic','score':40},{'area':'Investigative','score':35}]}
    ns['_onet_port']=lambda:SimpleNamespace(score_interest_profiler=score)
    with pytest.raises(Rerun):ns['render_onet_questionnaire']()
    assert len(calls)==1 and len(calls[0])==60
    assert s.onet_state['completed'] and s.navigation_page=='combined_results'
    if after_first_finalization:
        ui.pressed={'Acc\u00e9der \u00e0 mes rapports'}
        with pytest.raises(Rerun):ns['render_combined_results']()
        assert s.navigation_page=='finished'
    else:
        ui.pressed={'J\u2019ai consult\u00e9 mes r\u00e9sultats \u2014 donner mon ressenti'}
        with pytest.raises(Rerun):ns['render_combined_results']()
        assert s.navigation_page=='feeling'
        ui.pressed={'Valider mon ressenti'};ui.values={f'feel_{k}':4 for k in ('global','dominants','nuances','useful')}
        with pytest.raises(Rerun):ns['render_feeling']()
    ns['render_finished']()
    finals=[e for e in events(tmp_path) if e['event_type']=='TERMINE']
    assert [len(e['payload']['documents']) for e in finals]==([1,1] if after_first_finalization else [2])


def test_feedback_survives_failed_study_save_before_final_page(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state(RunMode.PUBLIC);verify_identity(s);s.feeling={}
    ns,ui=ui_namespace(s,pressed=['Valider mon ressenti'],values=dict({f'feel_{k}':4 for k in ('global','dominants','nuances','useful')},public_callback_choice='NON'))
    ns['save_public_study_record']=lambda *a:(_ for _ in ()).throw(PermissionError('private'))
    with pytest.raises(Rerun):ns['render_feeling']()
    assert s.feeling and s.navigation_page=='finished'
    assert 'private' not in str(ui.calls)
