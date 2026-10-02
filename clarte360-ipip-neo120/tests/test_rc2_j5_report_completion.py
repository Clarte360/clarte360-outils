from pathlib import Path
import hashlib
from pypdf import PdfReader
from clarte360_ipip.questionnaire import load_questionnaire
from clarte360_ipip.scoring import score_questionnaire
from clarte360_ipip.interpretation import load_interpretation, interpret_scoring
from clarte360_ipip.feedback import save_feedback
from clarte360_ipip.reporting import generate_report
from clarte360_ipip.completion import mark_completed, is_completed
from clarte360_ipip.connectors.gestion_actions import report_document_ref
BASE=Path(__file__).resolve().parents[1]
def _sample():
 root=BASE/'resources'/'ipip'; q=load_questionnaire(root/'REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json'); i=load_interpretation(root/'REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json'); answers={n:((n-1)%5)+1 for n in range(1,121)}; interp=interpret_scoring(score_questionnaire(q,answers),i); fb={'global':4,'dominants':4,'nuances':3,'useful':5,'over':'','under':'','dialogue':'oui','free':'À approfondir en séance.'}; return q,i,interp,fb
def _text(p): return '\n'.join(page.extract_text() or '' for page in PdfReader(str(p)).pages)
def test_j5_pdf_contains_required_clarte360_sections(tmp_path):
 q,i,interp,fb=_sample(); p=tmp_path/'report.pdf'; sha=generate_report(p,interpretation=interp,feedback=fb,app_version='0.8.0-rc2',reference_version=q.version,interpretation_version=i.version,beneficiary_identity={'first_name':'Alice','last_name':'Martin'},report_date='2026-10-02',logo_path=BASE/'assets'/'logo_clarte360.png'); assert sha==hashlib.sha256(p.read_bytes()).hexdigest(); text=_text(p)
 for expected in ['Alice Martin','2026-10-02','Vue d’ensemble','30 facettes','Points d’appui','À mettre en perspective avec mon parcours','Johnson, J. A. (2014)','D73, H690, D99 et D88','ne constitue pas une validation psychométrique française indépendante','Version application : 0.8.0-rc2']: assert expected in text
 assert len(PdfReader(str(p)).pages)>=7
def test_j5_pdf_values_match_interpretation_source(tmp_path):
 q,i,interp,fb=_sample(); p=tmp_path/'report.pdf'; generate_report(p,interpretation=interp,feedback=fb,app_version='0.8.0-rc2',reference_version=q.version,interpretation_version=i.version,logo_path=BASE/'assets'/'logo_clarte360.png'); text=_text(p)
 for d in interp['domains']: assert d['display_fr'] in text and f"{d['index_0_100']:.0f}/100" in text
 for f in interp['facets']: assert f['display_fr'] in text
def test_j5_completion_only_after_feedback_report_and_persistence(tmp_path):
 q,i,interp,fb=_sample(); run='RUN-J5'; assert not is_completed(tmp_path,run); save_feedback(tmp_path,run,fb); assert not is_completed(tmp_path,run); p=tmp_path/'reports'/f'{run}_v1.pdf'; sha=generate_report(p,interpretation=interp,feedback=fb,app_version='0.8.0-rc2',reference_version=q.version,interpretation_version=i.version,logo_path=BASE/'assets'/'logo_clarte360.png'); assert not is_completed(tmp_path,run); mark_completed(tmp_path,run,report_path=str(p),report_sha256=sha); assert is_completed(tmp_path,run); doc=report_document_ref(tmp_path,run); assert doc['mime_type']=='application/pdf' and doc['sha256']==sha and doc['size_bytes']==p.stat().st_size
def test_j5_identity_is_optional_and_not_inferred(tmp_path):
 q,i,interp,fb=_sample(); p=tmp_path/'anon.pdf'; generate_report(p,interpretation=interp,feedback=fb,app_version='0.8.0-rc2',reference_version=q.version,interpretation_version=i.version,logo_path=BASE/'assets'/'logo_clarte360.png'); assert 'Bénéficiaire :' not in _text(p)
