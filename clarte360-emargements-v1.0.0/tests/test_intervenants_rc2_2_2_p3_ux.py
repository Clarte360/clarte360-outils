from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
SERVICES=(ROOT/'services.py').read_text(encoding='utf-8')


def test_p3_app_parses():
    ast.parse(APP)


def test_p3_seven_business_tabs_and_ai_before_qualifications():
    expected="['Synthèse','Parcours professionnel','Conformité & collaboration','Analyse IA','Qualifications','Missions / Affectations','CV Clarté360']"
    assert expected in APP
    assert APP.index("'Analyse IA','Qualifications'") > 0


def test_p3_human_lock_removed_from_business_ui():
    assert "'Verrou humain':" not in APP
    assert "Verrouiller la validation humaine" not in APP


def test_p3_ai_prefill_is_not_human_validation():
    assert "Préremplir l’évaluation à partir de l’analyse IA" in APP
    fn=SERVICES[SERVICES.index('def decide_ai_criterion_proposal'):SERVICES.index('def list_ai_analysis_runs')]
    assert 'if accept: set_human_criterion_assessment(' not in fn
    assert 'accepting/classifying an AI proposal is not a human criterion validation' in fn


def test_p3_human_grid_and_final_validation_are_explicit():
    assert "Niveau retenu humain" in APP
    assert "Enregistrer l’évaluation humaine des critères" not in APP
    assert "Ces niveaux sont enregistrés avec la validation finale" in APP
    assert "Valider la qualification" in APP


def test_p3_review_points_are_actionable():
    for token in ['OUVERT','LEVE','CONFIRME','NON_PERTINENT']:
        assert token in APP
    assert 'decide_qualification_review_point' in APP


def test_p3_cockpit_and_missions_read_models_are_wired():
    assert 'professional_cockpit_summary(ENGINE,ppid)' in APP
    assert 'professional_missions_view(ENGINE,ppid)' in APP
    assert 'def professional_cockpit_summary' in SERVICES
    assert 'def professional_missions_view' in SERVICES


def test_p3_date_pickers_cover_key_dossier_dates():
    assert "date_input('Date de révision prévue" in APP
    assert "date_input('Valide jusqu’au (si applicable)'" in APP
    assert "date_input('Date de déclaration'" in APP

def test_p3_dossier_navigation_is_pilotable_for_deep_links():
    assert "screen=st.sidebar.radio('Navigation du dossier'" in APP
    assert "st.session_state[screen_key]='Qualifications'" in APP
    assert "st.session_state[screen_key]='Analyse IA'" in APP
    # The professional dossier no longer relies on a st.tabs container for its seven target screens.
    dossier=APP[APP.index("dossier_screens=['Synthèse'"):APP.index("if ps:",APP.index("dossier_screens=['Synthèse'"))]
    assert 'st.tabs(' not in dossier
