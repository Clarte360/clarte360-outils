import json
from pathlib import Path
import pytest
from clarte360_ipip.framework.validation import ValidationError
from clarte360_ipip.questionnaire import block_items, load_progress, load_questionnaire, save_progress, validate_answers

REF=Path('resources/ipip/REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json')

def test_reference_exactly_120_unique_ordered_items():
    q=load_questionnaire(REF); assert len(q.items)==120; assert [x.item_no for x in q.items]==list(range(1,121))

def test_scale_is_exactly_five_choices(): assert set(load_questionnaire(REF).response_scale)=={1,2,3,4,5}
def test_twelve_blocks_of_ten_cover_once():
    q=load_questionnaire(REF); nums=[i.item_no for b in range(12) for i in block_items(q,b,10)]; assert nums==list(range(1,121))
def test_no_political_johnson_o6_items_active():
    raw=json.loads(REF.read_text(encoding='utf-8')); o6=[x for x in raw['items'] if x['facet_code']=='O6']; assert len(o6)==4
    combined=' '.join((x.get('source_en','')+' '+x.get('adaptation_fr','')).lower() for x in o6)
    for word in ['liberal candidate','conservative candidate','vote for','candidat libéral','candidat conservateur']: assert word not in combined

def test_answer_bounds():
    assert validate_answers({1:1,120:5})=={1:1,120:5}
    with pytest.raises(ValidationError): validate_answers({1:6})

def test_save_and_resume_roundtrip(tmp_path):
    p=save_progress(tmp_path,'run-ABC_123',reference_version='1.0',answers={1:2,2:5},current_block=1); assert p.exists()
    x=load_progress(tmp_path,'run-ABC_123',expected_reference_version='1.0'); assert x['answers']=={1:2,2:5}; assert x['current_block']==1

def test_resume_refuses_reference_drift(tmp_path):
    save_progress(tmp_path,'run1',reference_version='1.0',answers={1:3},current_block=0)
    with pytest.raises(ValidationError): load_progress(tmp_path,'run1',expected_reference_version='2.0')

def test_jalon_b_questionnaire_contract_still_present(): assert Path('clarte360_ipip/questionnaire/model.py').exists()
