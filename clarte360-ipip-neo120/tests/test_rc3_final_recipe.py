from pathlib import Path
import inspect
from clarte360_ipip.reporting import beneficiary_report_filename
from clarte360_ipip.connectors.gestion_actions import report_document_ref
from clarte360_ipip.completion import mark_completed
import hashlib

BASE=Path(__file__).resolve().parents[1]

def test_human_report_filename():
    assert beneficiary_report_filename('Dominique','Briet') == 'D_BRIET_IPIP_NEO120_Profil_fonctionnement_professionnel.pdf'
    assert beneficiary_report_filename('Élodie','Dûpont-Martin') == 'E_DUPONT_MARTIN_IPIP_NEO120_Profil_fonctionnement_professionnel.pdf'

def test_document_reference_separates_storage_and_human_name(tmp_path):
    p=tmp_path/'reports'/'technical-run_v1.pdf'; p.parent.mkdir(); p.write_bytes(b'%PDF-safe')
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    mark_completed(tmp_path,'RUN-1',report_path=str(p),report_sha256=sha,report_version='0.8.0-rc3')
    ref=report_document_ref(tmp_path,'RUN-1',prescription_id='PRESC-1',display_file_name='D_BRIET_IPIP_NEO120_Profil_fonctionnement_professionnel.pdf')
    assert ref['storage_ref']=='reports/technical-run_v1.pdf'
    assert ref['file_name']=='D_BRIET_IPIP_NEO120_Profil_fonctionnement_professionnel.pdf'
    assert ref['display_name']==ref['file_name']
    assert ref['category_label']=='IPIP NEO 120 — Profil de fonctionnement professionnel'

def test_feedback_can_review_results_and_return_without_losing_draft():
    src=(BASE/'app.py').read_text(encoding='utf-8')
    assert "'feedback_draft':{}" in src
    assert "st.session_state.feedback_draft=current_draft" in src
    assert "st.session_state.stage='feedback_results'" in src
    assert "st.session_state.stage='feedback'; touch_activity('feedback_return')" in src
    assert 'Revoir mes résultats' in src and 'Retour à mon ressenti' in src

def test_download_and_ga_document_use_human_filename():
    src=(BASE/'app.py').read_text(encoding='utf-8')
    assert src.count('beneficiary_report_filename(') >= 3
    assert 'display_file_name=report_name' in src


def test_feedback_over_under_use_domains_only():
    src=(BASE/'app.py').read_text(encoding='utf-8')
    assert "domain_choices=['']+[x['display_fr'] for x in interp['domains']]" in src
    assert "facet_choices=" not in src
    assert 'Une grande dimension vous paraît-elle plus marquée que dans votre ressenti ? (facultatif)' in src
    assert 'Une grande dimension vous paraît-elle moins marquée que dans votre ressenti ? (facultatif)' in src
    assert "format_func=lambda x:'Aucun' if x=='' else x" in src


def test_report_receives_action_context_from_launch():
    src=(BASE/'app.py').read_text(encoding='utf-8')
    assert "action_context={'number': c.action_number, 'title': c.action_title}" in src
