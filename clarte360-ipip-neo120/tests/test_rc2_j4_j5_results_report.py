from pathlib import Path
import inspect
from pypdf import PdfReader
from clarte360_ipip.questionnaire import load_questionnaire
from clarte360_ipip.scoring import score_questionnaire
from clarte360_ipip.interpretation import load_interpretation, interpret_scoring
from clarte360_ipip.reporting import generate_report
from clarte360_ipip.version import APP_VERSION
BASE=Path(__file__).resolve().parents[1]

def sample():
    q=load_questionnaire(BASE/'resources/ipip/REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json')
    r=load_interpretation(BASE/'resources/ipip/REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json')
    interp=interpret_scoring(score_questionnaire(q,{i:(i%5)+1 for i in range(1,121)}),r)
    fb={'global':4,'dominants':4,'nuances':3,'useful':5,'over':'','under':'','dialogue':'oui','free':'À approfondir.'}
    return q,r,interp,fb

def test_results_ui_no_streamlit_progress_bars():
    src=(BASE/'clarte360_ipip/ui/results.py').read_text(encoding='utf-8')
    assert 'st.progress' not in src
    assert "Vue d'ensemble" in src and '30 facettes' in src and 'À mettre en perspective avec mon parcours' in src

def test_report_contains_framework_sections_logo_and_limits(tmp_path):
    q,r,interp,fb=sample(); out=tmp_path/'report.pdf'
    sha=generate_report(out,interpretation=interp,feedback=fb,app_version=APP_VERSION,reference_version=q.version,interpretation_version=r.version,beneficiary_identity={'first_name':'Camille','last_name':'Exemple'})
    assert len(sha)==64 and out.stat().st_size>12000
    text='\n'.join((p.extract_text() or '') for p in PdfReader(str(out)).pages)
    for expected in ['Profil de fonctionnement professionnel','Camille Exemple','Vue d’ensemble','Lecture détaillée','À mettre en perspective avec mon parcours','Mon ressenti','Johnson','Ouverture aux conventions','diagnostic psychologique ou psychiatrique']:
        assert expected in text

def test_report_values_match_interpretation(tmp_path):
    q,r,interp,fb=sample(); out=tmp_path/'report.pdf'
    generate_report(out,interpretation=interp,feedback=fb,app_version=APP_VERSION,reference_version=q.version,interpretation_version=r.version)
    text='\n'.join((p.extract_text() or '') for p in PdfReader(str(out)).pages)
    for d in interp['domains']:
        assert d['display_fr'] in text
        assert f"{d['index_0_100']:.0f}/100" in text

def test_report_explicitly_denies_percentile_and_french_norm_status():
    src=inspect.getsource(generate_report).lower()
    assert "ni d’un percentile" in src or "ni d'un percentile" in src
    assert 'ni d’une norme française' in src or "ni d'une norme française" in src
