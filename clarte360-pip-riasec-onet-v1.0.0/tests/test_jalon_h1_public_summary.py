from pathlib import Path
import subprocess
from clarte360_pip.domain.models import LaunchContext, RunMode
from clarte360_pip.reporting import build_pip_report_pdf, PIP_REPORT_VERSION

def session(mode):
    if mode is RunMode.ACCOMPANIMENT:
        launch=LaunchContext(mode=mode,beneficiary_id='B',action_id='A',prescription_id='P',beneficiary_first_name='Exemple',beneficiary_last_name='Beneficiaire')
    else: launch=LaunchContext(mode=mode)
    answers={f'PIP-{d}-{i:02d}':3 for d in 'RIASEC' for i in range(1,13)}
    # use actual bank ids instead
    import json
    root=Path(__file__).resolve().parents[1]
    bank=json.loads((root/'resources/runtime/pip_bank_PIP-BANK-0.5.json').read_text())
    answers={it['item_id']:(1+(i%5)) for i,it in enumerate(bank['items'])}
    return {'launch_context':launch,'public_identity':{'first_name':'Exemple','last_name':'Public'},'pip_state':{'answers':answers},'pip_scoring':{'complete':True,'indices':{'R':31,'I':28,'A':26,'S':22,'E':18,'C':14},'order':['R','I','A','S','E','C'],'holland_code':'RIA','algorithm_version':'PIP-SCORE-0.5'}}

def pages(pdf,tmp_path,name):
    p=tmp_path/name; p.write_bytes(pdf)
    out=subprocess.check_output(['pdfinfo',str(p)],text=True)
    return int(next(x.split(':',1)[1] for x in out.splitlines() if x.startswith('Pages:')).strip())

def text(pdf,tmp_path,name):
    p=tmp_path/name; p.write_bytes(pdf); o=tmp_path/(name+'.txt'); subprocess.run(['pdftotext',str(p),str(o)],check=True); return o.read_text(errors='ignore')

def test_h1_public_is_five_pages_and_accompaniment_remains_nine(tmp_path):
    assert pages(build_pip_report_pdf(session(RunMode.PUBLIC)),tmp_path,'pub.pdf')==5
    assert pages(build_pip_report_pdf(session(RunMode.ACCOMPANIMENT)),tmp_path,'acc.pdf')==9

def test_h1_public_is_synthesis_not_full_accompaniment(tmp_path):
    t=text(build_pip_report_pdf(session(RunMode.PUBLIC)),tmp_path,'pub2.pdf')
    assert 'Quelques facettes qui nuancent votre profil' in t
    assert 'Vos 30 facettes Clarté360' not in t
    assert 'Utiliser ce rapport dans votre accompagnement' not in t
    assert 'quatre exemples au maximum' in t.lower()

def test_h1_accompaniment_keeps_full_facets(tmp_path):
    t=text(build_pip_report_pdf(session(RunMode.ACCOMPANIMENT)),tmp_path,'acc2.pdf')
    assert 'Vos 30 facettes Clarté360' in t
    assert 'Utiliser ce rapport dans votre' in t and 'accompagnement' in t

def test_h1_report_version(): assert PIP_REPORT_VERSION=='PIP-RPT-1.6'
