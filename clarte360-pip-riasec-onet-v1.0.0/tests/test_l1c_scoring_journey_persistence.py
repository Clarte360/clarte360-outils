from clarte360_pip.pip_data.loader import load_pip_bank
from clarte360_pip.scoring import score_pip
from clarte360_pip.journey import results_allowed,next_after_pip
from clarte360_pip.feeling import build_feeling_record,QUESTIONS
from clarte360_pip.framework.persistence import build_snapshot,validate_snapshot

def answers_by_dim(bank, values): return {x['item_id']:values[x['dimension']] for x in bank['items']}
def test_scoring_formula_and_code():
 b=load_pip_bank(); r=score_pip(b,answers_by_dim(b,{'R':5,'I':4,'A':3,'S':2,'E':1,'C':1}))
 assert r.complete and r.means['R']==5 and r.indices['R']==100 and r.indices['A']==50 and r.holland_code=='RIA'
def test_exact_tie_not_arbitrarily_coded():
 b=load_pip_bank(); r=score_pip(b,answers_by_dim(b,{'R':5,'I':5,'A':4,'S':3,'E':2,'C':1}))
 assert r.holland_code is None and ['R','I'] in r.exact_ties
def test_tie_at_third_blocks_code():
 b=load_pip_bank(); r=score_pip(b,answers_by_dim(b,{'R':5,'I':4,'A':3,'S':3,'E':2,'C':1}))
 assert r.holland_code is None
def test_incomplete_blocks_complete():
 b=load_pip_bank(); r=score_pip(b,{b['items'][0]['item_id']:5}); assert not r.complete
def test_journey_anti_influence():
 assert results_allowed('PIP_SEUL',True)
 assert not results_allowed('PIP_PUIS_ONET60',True,False)
 assert results_allowed('PIP_PUIS_ONET60',True,True)
 assert next_after_pip('PIP_PUIS_ONET60')=='onet_pending'
def test_feeling_is_closed_and_separate():
 assert len(QUESTIONS)==7
 rec=build_feeling_record({'global':4},'PUBLIC'); assert rec['answers']['global']==4
def test_snapshot_v1():
 d={'passation_id':'p1','journey':'PIP_SEUL','pip_state':{},'pip_scoring':{},'feeling':{}}
 snap=build_snapshot(d); assert snap['schema']=='clarte360.pip.run.v1' and validate_snapshot(snap)==[]
