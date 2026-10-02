import json
from pathlib import Path

import pytest

from clarte360_ipip.framework.validation import ValidationError
from clarte360_ipip.questionnaire import (
    first_unanswered,
    item_at,
    load_progress,
    load_questionnaire,
    next_item,
    previous_item,
    resume_item,
    save_progress,
)

REF=Path('resources/ipip/REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json')


def test_j3_one_item_navigation_covers_1_to_120():
    q=load_questionnaire(REF)
    assert [item_at(q,n).item_no for n in range(1,121)] == list(range(1,121))
    assert previous_item(1)==1 and previous_item(2)==1
    assert next_item(119)==120 and next_item(120)==120


def test_j3_resume_exact_item_roundtrip(tmp_path):
    save_progress(tmp_path,'run-j3',reference_version='1.0',answers={1:2,2:4,3:5},current_item=4)
    x=load_progress(tmp_path,'run-j3',expected_reference_version='1.0')
    assert x['answers']=={1:2,2:4,3:5}
    assert x['current_item']==4
    assert resume_item(x['answers'],x['current_item'])==4


def test_j3_backward_compatibility_with_legacy_block_snapshot(tmp_path):
    p=tmp_path/'runs'/'legacy.json'; p.parent.mkdir(parents=True)
    payload={
        'schema':'clarte360.ipipneo.questionnaire.v1','run_id':'legacy','reference_version':'1.0',
        'answers':{str(n):3 for n in range(1,14)},'current_block':1,'updated_at':'2026-10-01T00:00:00+00:00'
    }
    p.write_text(json.dumps(payload),encoding='utf-8')
    x=load_progress(tmp_path,'legacy',expected_reference_version='1.0')
    assert x['current_item']==14


def test_j3_first_unanswered_detects_gap():
    assert first_unanswered({1:3,2:4,4:5})==3
    assert first_unanswered({n:3 for n in range(1,121)},default=120)==120


def test_j3_invalid_current_item_is_rejected(tmp_path):
    with pytest.raises(ValidationError):
        save_progress(tmp_path,'run-j3',reference_version='1.0',answers={},current_item=121)


def test_j3_ui_is_one_affirmation_at_a_time():
    src=Path('app.py').read_text(encoding='utf-8')
    ui=Path('clarte360_ipip/ui/questionnaire.py').read_text(encoding='utf-8')
    assert "render_question(q,item_no" in src
    assert "QUESTION {item_no} / {TOTAL_ITEMS}" in ui
    assert "← PRÉCÉDENT" in src and "SUIVANT →" in src
    assert "Bloc précédent" not in src
    assert "Répondez aux 10 affirmations" not in src
    assert "block_items(q" not in src


def test_j3_no_score_or_domain_exposed_by_question_component():
    ui=Path('clarte360_ipip/ui/questionnaire.py').read_text(encoding='utf-8').lower()
    for forbidden in ['facet_code','domain_code','score_questionnaire','index_0_100','tendency_label']:
        assert forbidden not in ui


def test_j3_response_scale_is_read_from_master_reference():
    q=load_questionnaire(REF)
    ui=Path('clarte360_ipip/ui/questionnaire.py').read_text(encoding='utf-8')
    assert set(q.response_scale)=={1,2,3,4,5}
    assert 'q.response_scale[x]' in ui


def test_j3_mobile_and_keyboard_friendly_framework_css_present():
    css=Path('clarte360_ipip/framework/branding.py').read_text(encoding='utf-8')
    assert '@media (max-width: 640px)' in css
    assert 'min-height:2.7rem' in css
    assert 'radiogroup' in css
