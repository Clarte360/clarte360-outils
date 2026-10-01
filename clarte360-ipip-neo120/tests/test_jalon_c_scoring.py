from pathlib import Path
import pytest
from clarte360_ipip.framework.validation import ValidationError
from clarte360_ipip.questionnaire import load_questionnaire
from clarte360_ipip.scoring import ALGORITHM_VERSION, score_questionnaire

REF=Path('resources/ipip/REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json')
Q=load_questionnaire(REF)

def test_requires_120_answers():
    with pytest.raises(ValidationError): score_questionnaire(Q,{1:3})

def test_all_three_is_neutral_everywhere():
    r=score_questionnaire(Q,{i:3 for i in range(1,121)})
    assert len(r.facets)==30 and len(r.domains)==5
    assert all(x.mean==3 and x.corrected_sum==12 and x.index_0_100==50 for x in r.facets.values())
    assert all(x.mean==3 and x.corrected_sum==72 and x.index_0_100==50 for x in r.domains.values())

def test_reverse_key_is_exactly_six_minus_response():
    answers={i:3 for i in range(1,121)}
    pos=next(x for x in Q.items if not x.reverse_scored); neg=next(x for x in Q.items if x.reverse_scored)
    answers[pos.item_no]=5; answers[neg.item_no]=5
    r=score_questionnaire(Q,answers)
    assert r.corrected_items[pos.item_no]==5
    assert r.corrected_items[neg.item_no]==1

def test_all_one_and_all_five_respect_polarities():
    r1=score_questionnaire(Q,{i:1 for i in range(1,121)})
    r5=score_questionnaire(Q,{i:5 for i in range(1,121)})
    for item in Q.items:
        assert r1.corrected_items[item.item_no] == (5 if item.reverse_scored else 1)
        assert r5.corrected_items[item.item_no] == (1 if item.reverse_scored else 5)

def test_each_facet_exactly_four_and_domain_exactly_six_facets():
    r=score_questionnaire(Q,{i:3 for i in range(1,121)})
    assert all(len(x.item_numbers)==4 for x in r.facets.values())
    assert all(len(x.facet_codes)==6 for x in r.domains.values())

def test_domain_mean_equals_mean_of_facets():
    answers={i:((i-1)%5)+1 for i in range(1,121)}
    r=score_questionnaire(Q,answers)
    for d,x in r.domains.items():
        assert x.mean == pytest.approx(sum(r.facets[c].mean for c in x.facet_codes)/6)

def test_index_is_linear_not_percentile():
    r=score_questionnaire(Q,{i:3 for i in range(1,121)})
    assert all(x.index_0_100==50 for x in r.facets.values())
    assert ALGORITHM_VERSION=='ipip-scoring-v1'

def test_o6_uses_exactly_four_active_items():
    r=score_questionnaire(Q,{i:3 for i in range(1,121)})
    assert len(r.facets['O6'].item_numbers)==4

def test_scoring_serialization_has_versions():
    r=score_questionnaire(Q,{i:3 for i in range(1,121)}).to_dict()
    assert r['algorithm_version']=='ipip-scoring-v1'
    assert r['reference_version']=='1.0'
    assert len(r['facets'])==30 and len(r['domains'])==5 and len(r['corrected_items'])==120

def test_beneficiary_ui_does_not_expose_resume_code_by_default():
    text=Path('app.py').read_text(encoding='utf-8')
    assert 'Code de reprise' not in text
    assert 'Reprendre une sauvegarde technique' not in text  # mode ACCOMPAGNEMENT: reprise automatique par prescription
