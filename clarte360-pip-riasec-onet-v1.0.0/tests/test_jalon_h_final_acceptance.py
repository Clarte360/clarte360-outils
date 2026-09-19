from pathlib import Path
import subprocess, sys
from clarte360_pip.domain.models import LaunchContext, RunMode
from clarte360_pip.pip_data.loader import load_pip_bank
from clarte360_pip.reporting import build_pip_report_pdf, PIP_REPORT_VERSION, ONET_REPORT_VERSION
from clarte360_pip.version import JALON_ID, BUILD_INCREMENT, PIP_BANK_VERSION, PIP_INTERPRETATION_VERSION

ROOT=Path(__file__).resolve().parents[1]

def _session(mode):
    bank=load_pip_bank(); answers={x['item_id']:(1+(i%5)) for i,x in enumerate(bank['items'])}
    if mode is RunMode.ACCOMPANIMENT:
        launch=LaunchContext(mode=mode, beneficiary_id='BEN-TEST', action_id='ACT-TEST', prescription_id='PRE-TEST', beneficiary_first_name='Test', beneficiary_last_name='Beneficiaire', action_number='CLA-TEST', action_title='Bilan de competences')
    else:
        launch=LaunchContext(mode=mode)
    return {'launch_context':launch,'public_identity':{'first_name':'Test','last_name':'Public'},'pip_state':{'answers':answers,'bank_version':bank['bank_version']},'pip_scoring':{'complete':True,'indices':{'R':31,'I':28,'A':26,'S':22,'E':18,'C':14},'order':['R','I','A','S','E','C'],'holland_code':'RIA','algorithm_version':'PIP-SCORE-0.5'}}

def _text(pdf,tmp_path,name):
    p=tmp_path/name; p.write_bytes(pdf); out=tmp_path/(name+'.txt')
    subprocess.run(['pdftotext',str(p),str(out)],check=True)
    return ' '.join(out.read_text(encoding='utf-8',errors='ignore').split())

def test_final_versions():
    assert JALON_ID=='H3.1'; assert BUILD_INCREMENT=='L1-H3.1-STUDY-ID-RESUME-IDEMPOTENCE'
    assert PIP_BANK_VERSION=='PIP-BANK-0.5'; assert PIP_INTERPRETATION_VERSION=='PIP-INT-1.0'
    assert PIP_REPORT_VERSION=='PIP-RPT-1.6'; assert ONET_REPORT_VERSION=='ONET-RPT-1.1'

def test_public_pdf_has_required_prudence(tmp_path):
    txt=_text(build_pip_report_pdf(_session(RunMode.PUBLIC)),tmp_path,'public.pdf')
    assert 'support d’exploration' in txt
    assert 'prescription d’orientation' in txt
    assert 'validation de compétences' in txt

def test_accompaniment_pdf_has_mandatory_cdc_notice(tmp_path):
    txt=_text(build_pip_report_pdf(_session(RunMode.ACCOMPANIMENT)),tmp_path,'accomp.pdf')
    assert 'Ce document constitue une étape de votre processus' in txt
    assert 'destinés à être mis en perspective avec les autres éléments' in txt
    assert 'ne détermine pas' in txt and 'choix de métier' in txt

def test_final_source_sync_checks():
    for script in ('build_pip_runtime.py','build_interpretation_runtime.py','build_rome_runtime.py'):
        p=subprocess.run([sys.executable,str(ROOT/'scripts'/script),'--check'],cwd=ROOT,capture_output=True,text=True)
        assert p.returncode==0,p.stdout+p.stderr
