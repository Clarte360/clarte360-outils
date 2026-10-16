import ast
from pathlib import Path
source=(Path(__file__).parents[1]/'clarte360_pip/ui/pages.py').read_text()
module=ast.parse(source)
function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='_finalization_requirements_met')
function.returns=None
for arg in function.args.args: arg.annotation=None
namespace={}
exec(compile(ast.Module(body=[function],type_ignores=[]),'<guard>','exec'),namespace)
_finalization_requirements_met=namespace['_finalization_requirements_met']


def state(journey='PIP_SEUL', onet=False):
    return {'journey':journey,'pip_state':{'completed':True},'pip_scoring':{'complete':True},
            'onet_state':{'completed':onet},'restitution_presented':True,
            'feeling':{'answers':{'global':4,'dominants':3,'nuances':5,'useful':4}}}


def test_pip_alone_may_finalize_after_feeling():
    assert _finalization_requirements_met(state())


def test_pip_and_onet_must_finish_both():
    assert not _finalization_requirements_met(state('PIP_PUIS_ONET60'))
    assert _finalization_requirements_met(state('PIP_PUIS_ONET60', True))


def test_missing_feeling_or_pip_blocks_finalization():
    s=state();s['feeling']={};assert not _finalization_requirements_met(s)
    s=state();s['pip_state']['completed']=False;assert not _finalization_requirements_met(s)
    s=state();s['restitution_presented']=False;assert not _finalization_requirements_met(s)


def test_onet_has_no_feeling_and_pip_has_preview():
    from pathlib import Path
    src=(Path(__file__).parents[1]/'clarte360_pip/ui/pages.py').read_text()
    assert 'Consulter mon rapport PIP pendant mon ressenti' in src
    assert 'rapport_onet_interest_profiler.pdf' in src
    assert 'ressenti concerne uniquement le PIP' in src
