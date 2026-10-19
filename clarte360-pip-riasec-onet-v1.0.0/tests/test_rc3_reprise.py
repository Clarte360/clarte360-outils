import ast
import copy
import json
import logging
import os
import stat
from pathlib import Path
from types import SimpleNamespace
import pytest
from clarte360_pip.framework import server_store as store, resume
from clarte360_pip.framework.storage_io import atomic_json
from clarte360_pip.framework.persistence import build_snapshot,restore_snapshot
from rc3_support import State,make_state,isolate


def unfinished(s):
    s.pip_state['answers'].pop(s.pip_state['order'][-1]);s.pip_state['completed']=False;s.pip_scoring={};s.feeling={};s.restitution_presented=False
    s.navigation_page=s.last_useful_page='pip_questionnaire'
    return s


def save(s):
    c=s.launch_context
    return store.save_accompanied_snapshot(s,c.action_id,c.beneficiary_id,c.prescription_id)


def test_71_answers_restore_on_question_72(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=unfinished(make_state());save(s)
    restored=State(passation_id='NEW-UUID',pip_state={})
    assert resume.restore_accompanied(s.launch_context,restored)
    assert restored.passation_id==s.passation_id and len(restored.pip_state['answers'])==71
    assert restored.pip_state['index']==71 and restored.navigation_page=='pip_questionnaire'

@pytest.mark.parametrize('exception',[PermissionError('private path'),ValueError('sensitive state'),FileNotFoundError('private path')])
def test_read_error_blocks_new_run_without_mutating_state(monkeypatch,tmp_path,exception,caplog):
    isolate(monkeypatch,tmp_path);s=unfinished(make_state());save(s)
    p=store.prescription_pointer_path(s.launch_context.prescription_id);before=p.read_bytes()
    monkeypatch.setattr(resume,'load_latest_accompanied_snapshot',lambda *a:(_ for _ in ()).throw(exception))
    other=State(passation_id='NEW',pip_state={})
    with caplog.at_level(logging.ERROR): assert not resume.restore_accompanied(s.launch_context,other)
    assert not other.server_resume_checked and other.server_resume_error
    assert p.read_bytes()==before and 'sensitive' not in caplog.text and 'private path' not in caplog.text
    with pytest.raises(store.SnapshotConflict): store.save_accompanied_snapshot(other,'TEST-A','TEST-B','TEST-PRES')
    assert p.read_bytes()==before


def test_stale_new_run_cannot_replace_pointer(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=unfinished(make_state());save(s)
    other=unfinished(make_state(run='OTHER'))
    with pytest.raises(store.SnapshotConflict):save(other)
    assert store.load_latest_accompanied_snapshot('TEST-A','TEST-B','TEST-PRES')['passation_id']==s.passation_id
    assert not store.accompanied_run_path('TEST-A','TEST-B','OTHER').exists()


def test_stale_progress_cannot_erase_answers(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=unfinished(make_state());save(s);s.pip_state['answers']={}
    with pytest.raises(store.SnapshotConflict): save(s)
    assert len(store.load_latest_accompanied_snapshot('TEST-A','TEST-B','TEST-PRES')['pip_state']['answers'])==71


def test_crossed_scope_is_rejected(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=unfinished(make_state());save(s)
    p=store.accompanied_run_path('TEST-A','TEST-B',s.passation_id);obj=json.loads(p.read_text());obj['launch_context']['beneficiary_id']='OTHER';p.write_text(json.dumps(obj))
    target=State(passation_id='NEW')
    assert not resume.restore_accompanied(s.launch_context,target)
    assert target.passation_id=='NEW'


def test_new_prescription_has_independent_passation(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=unfinished(make_state());save(s)
    other=unfinished(make_state(run='RUN-B',prescription='PRES-B'));save(other)
    assert len(list((tmp_path/'accompanied_runs'/'_prescriptions').glob('*.json')))==2


def test_atomic_json_preserves_mode_and_owner(tmp_path):
    p=tmp_path/'state.json';p.write_text('{}');p.chmod(0o640);before=p.stat()
    atomic_json(p,{'ok':True});after=p.stat()
    assert stat.S_IMODE(after.st_mode)==0o640 and after.st_uid==before.st_uid and after.st_gid==before.st_gid


def test_atomic_json_refuses_symlink(tmp_path):
    p=tmp_path/'original';p.write_text('{}');link=tmp_path/'link';link.symlink_to(p)
    with pytest.raises(ValueError):atomic_json(link,{'bad':True})
    assert p.read_text()=='{}'


def test_context_change_clears_widgets_and_old_responses():
    source=(Path(__file__).parents[1]/'clarte360_pip/framework/session.py').read_text()
    module=ast.parse(source);fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='initialize_session')
    a=make_state();b=make_state(run='B',prescription='OTHER')
    state=State(a);state['feel_global']=5;state['server_resume_checked']=True
    from clarte360_pip.domain import LaunchContext
    from uuid import uuid4
    ns={'LaunchContext':LaunchContext,'st':SimpleNamespace(session_state=state),'uuid4':uuid4,'now_iso':lambda:'now'}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<init>','exec'),ns)
    ns['initialize_session'](b.launch_context)
    assert state.launch_context==b.launch_context and state.pip_state=={} and 'feel_global' not in state and 'server_resume_checked' not in state


def test_missing_pointer_target_is_not_treated_as_new(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=unfinished(make_state());save(s)
    store.accompanied_run_path('TEST-A','TEST-B',s.passation_id).unlink()
    target=State(passation_id='NEW')
    assert not resume.restore_accompanied(s.launch_context,target)
    assert target.passation_id=='NEW'
