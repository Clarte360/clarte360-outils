from pathlib import Path
import json
from clarte360_ipip.questionnaire import load_questionnaire
from clarte360_ipip.scoring import score_questionnaire
from clarte360_ipip.interpretation import load_interpretation, interpret_scoring
from clarte360_ipip.feedback import validate_feedback, save_feedback, load_feedback
from clarte360_ipip.reporting import generate_report
from clarte360_ipip.completion import mark_completed, is_completed, load_completion
from clarte360_ipip.version import APP_VERSION
BASE=Path(__file__).resolve().parents[1]

def sample():
    q=load_questionnaire(BASE/'resources/ipip/REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json')
    r=load_interpretation(BASE/'resources/ipip/REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json')
    interp=interpret_scoring(score_questionnaire(q,{i:(i%5)+1 for i in range(1,121)}),r)
    fb={'global':4,'dominants':4,'nuances':3,'useful':5,'over':'','under':'','dialogue':'oui','free':'À approfondir.'}
    return q,r,interp,fb

def test_feedback_validation_and_persistence(tmp_path):
    _,_,_,fb=sample(); clean=validate_feedback(fb); assert clean['global']==4
    save_feedback(tmp_path,'abc123',fb); assert load_feedback(tmp_path,'abc123')['dialogue']=='oui'

def test_report_pdf_and_completion_lock(tmp_path):
    q,r,interp,fb=sample(); p=tmp_path/'reports'/'x.pdf'
    sha=generate_report(p,interpretation=interp,feedback=fb,app_version=APP_VERSION,reference_version=q.version,interpretation_version=r.version)
    assert p.read_bytes().startswith(b'%PDF') and p.stat().st_size>10000 and len(sha)==64
    mark_completed(tmp_path,'abc123',report_path=str(p),report_sha256=sha)
    assert is_completed(tmp_path,'abc123')
    assert load_completion(tmp_path,'abc123')['status']=='TERMINE'

def test_feedback_does_not_change_scoring():
    q,_,_,fb=sample(); a={i:3 for i in range(1,121)}
    before=score_questionnaire(q,a).to_dict(); validate_feedback(fb); after=score_questionnaire(q,a).to_dict(); assert before==after
