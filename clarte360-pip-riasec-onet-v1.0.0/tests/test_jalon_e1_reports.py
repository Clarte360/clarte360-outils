from clarte360_pip.reporting import build_pip_report_pdf, build_onet_report_pdf, PIP_REPORT_VERSION, ONET_REPORT_VERSION, facet_indicators
from clarte360_pip.pip_data.loader import load_pip_bank

def sample(with_onet=True):
    b=load_pip_bank(); answers={x['item_id']:(1+(i%5)) for i,x in enumerate(b['items'])}
    d={'pip_state':{'answers':answers,'bank_version':b['bank_version']},'pip_scoring':{'complete':True,'indices':{'R':80,'I':70,'A':60,'S':50,'E':40,'C':30},'order':['R','I','A','S','E','C'],'holland_code':'RIA','algorithm_version':'PIP-SCORE-0.5'}}
    if with_onet:d['onet_state']={'completed':True,'results':[{'code':'realistic','title':'Realistic','score':30},{'code':'investigative','title':'Investigative','score':25},{'code':'artistic','title':'Artistic','score':20},{'code':'social','title':'Social','score':15},{'code':'enterprising','title':'Enterprising','score':10},{'code':'conventional','title':'Conventional','score':5}]}
    return d

def test_pip_report_is_autonomous_and_has_facets():
    s=sample(); b=build_pip_report_pdf(s); assert b.startswith(b'%PDF'); assert len(b)>10000; assert len(facet_indicators(s))==30

def test_onet_report_is_separate():
    b=build_onet_report_pdf(sample()); assert b.startswith(b'%PDF'); assert len(b)>7000

def test_onet_required():
    import pytest
    with pytest.raises(ValueError): build_onet_report_pdf(sample(False))

def test_versions(): assert PIP_REPORT_VERSION=='PIP-RPT-1.6' and ONET_REPORT_VERSION=='ONET-RPT-1.1'
