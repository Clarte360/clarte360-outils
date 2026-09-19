from clarte360_pip.interpretation import score_band, profile_shape, interpret_pip
from clarte360_pip.reporting import PIP_REPORT_VERSION, ONET_REPORT_VERSION

def test_31_is_not_strong_dominance():
    x=interpret_pip({'R':31,'I':28,'A':26,'S':24,'E':22,'C':20},list('RIAS EC'.replace(' ','')))
    assert 'aucune forte dominante' in x['headline']
    assert score_band(31)['label']=='plutôt peu marqué'

def test_93_87_is_two_close_high_poles():
    order=['S','A','I','E','R','C']; vals={'S':93,'A':87,'I':48,'E':42,'R':35,'C':30}
    x=interpret_pip(vals,order)
    assert 'Deux dimensions' in x['headline']
    assert x['shape']['gap12']==6
    # Six points is close enough to remain a two-pole reading in narrative only when both are high;
    # generic shape rule labels it as a slightly detached first dimension.
    assert x['bands']['S']['label']=='très marqué'

def test_93_52_is_detached():
    order=['S','A','I','E','R','C']; vals={'S':93,'A':52,'I':41,'E':35,'R':30,'C':20}
    x=interpret_pip(vals,order)
    assert 'très marquée' in x['headline']
    assert x['shape']['gap12']==41

def test_flat_profile():
    order=list('RIASEC'); vals={'R':62,'I':60,'A':58,'S':57,'E':55,'C':53}
    assert profile_shape(vals,order)['relief']=='très homogène'

def test_report_versions_e2():
    assert PIP_REPORT_VERSION=='PIP-RPT-1.6'
    assert ONET_REPORT_VERSION=='ONET-RPT-1.1'
