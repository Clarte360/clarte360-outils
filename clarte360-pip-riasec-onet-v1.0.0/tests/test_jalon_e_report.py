from clarte360_pip.reporting import build_report_pdf, REPORT_VERSION

def sample(onet=False, feeling=False):
    d={"pip_scoring":{"complete":True,"indices":{"R":80,"I":70,"A":60,"S":50,"E":40,"C":30},"order":["R","I","A","S","E","C"],"holland_code":"RIA","algorithm_version":"PIP-SCORE-0.5"}}
    if onet: d["onet_state"]={"completed":True,"results":[{"code":"realistic","title":"Realistic","score":30},{"code":"investigative","title":"Investigative","score":25},{"code":"artistic","title":"Artistic","score":20},{"code":"social","title":"Social","score":15},{"code":"enterprising","title":"Enterprising","score":10},{"code":"conventional","title":"Conventional","score":5}]}
    if feeling: d["feeling"]={"questions":{"global":{"text":"Profil ressemblant ?"}},"answers":{"global":5}}
    return d

def test_pdf_pip_only():
    b=build_report_pdf(sample()); assert b.startswith(b'%PDF'); assert len(b)>5000

def test_pdf_with_onet_and_feeling():
    b=build_report_pdf(sample(True,True)); assert b.startswith(b'%PDF'); assert len(b)>7000

def test_report_version(): assert REPORT_VERSION=='PIP-RPT-1.6'
