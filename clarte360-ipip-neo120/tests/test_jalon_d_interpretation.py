from pathlib import Path
from clarte360_ipip.interpretation import load_interpretation, tendency_band, interpret_scoring
from clarte360_ipip.questionnaire import load_questionnaire
from clarte360_ipip.scoring import score_questionnaire
BASE=Path(__file__).resolve().parents[1]

def test_reference_complete():
    r=load_interpretation(BASE/'resources/ipip/REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json')
    assert len(r.domains)==5 and len(r.facets)==30
    assert r.domains['N']['display_fr']=='Sensibilité émotionnelle'
    assert r.facets['O6']['display_fr']=='Ouverture aux conventions'

def test_bands_are_descriptive():
    assert tendency_band(2.49)=='less'
    assert tendency_band(2.5)=='intermediate'
    assert tendency_band(3.5)=='intermediate'
    assert tendency_band(3.51)=='more'

def test_interpretation_has_5_and_30():
    q=load_questionnaire(BASE/'resources/ipip/REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json')
    r=load_interpretation(BASE/'resources/ipip/REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json')
    out=interpret_scoring(score_questionnaire(q,{i:3 for i in range(1,121)}),r)
    assert len(out['domains'])==5 and len(out['facets'])==30
    assert all(x['tendency_band']=='intermediate' for x in out['domains'])
    assert 'non_normative_notice' in out
