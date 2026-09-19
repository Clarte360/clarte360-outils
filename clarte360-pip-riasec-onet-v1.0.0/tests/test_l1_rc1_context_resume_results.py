import json
from pathlib import Path
from clarte360_pip.pip_data.loader import load_pip_bank
from clarte360_pip.framework.persistence import build_snapshot, restore_snapshot
from clarte360_pip.journey import results_allowed

ROOT=Path(__file__).resolve().parents[1]

def test_72_concrete_items_are_present_without_separate_examples():
    bank=load_pip_bank()
    assert len(bank['items'])==72
    assert len({x['item_id'] for x in bank['items']})==72
    assert all(isinstance(x.get('texte_fr'),str) and x['texte_fr'].strip() for x in bank['items'])
    assert all('exemple_concret' not in x for x in bank['items'])

def test_first_item_is_concrete_v05():
    bank=load_pip_bank()
    assert 'Assembler plusieurs pièces' in bank['items'][0]['texte_fr']

def test_mid_passation_snapshot_restores_index_order_answers():
    state={'passation_id':'p1','session_id':'s1','navigation_page':'pip_questionnaire','journey':'PIP_SEUL','pip_state':{'bank_version':'PIP-BANK-0.4','order':['a','b','c'],'answers':{'a':4,'b':2},'index':1},'pip_scoring':{},'onet_state':{},'feeling':{},'session_history':[]}
    payload=build_snapshot(state)
    target={}
    restore_snapshot(payload,target)
    assert target['navigation_page']=='pip_questionnaire'
    assert target['pip_state']['index']==1
    assert target['pip_state']['answers']=={'a':4,'b':2}
    assert target['pip_state']['order']==['a','b','c']

def test_pip_only_results_allowed_after_completion_but_onet_path_stays_locked():
    assert results_allowed('PIP_SEUL',True,False)
    assert not results_allowed('PIP_PUIS_ONET60',True,False)
    assert results_allowed('PIP_PUIS_ONET60',True,True)

def test_brand_logo_is_carried_in_assets():
    p=ROOT/'assets'/'logo_clarte360.png'
    assert p.is_file() and p.stat().st_size>1000
