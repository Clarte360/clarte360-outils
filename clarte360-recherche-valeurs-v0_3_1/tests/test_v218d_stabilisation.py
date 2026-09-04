from pathlib import Path
import ast

APP=Path(__file__).resolve().parents[1]/'app.py'
TEXT=APP.read_text(encoding='utf-8')

def test_version_8d_and_single_explicit_validation_engine():
    assert 'APP_VERSION = "2.2.0-preproduction-2"' in TEXT
    assert 'Retourne uniquement une réponse explicitement validée' in TEXT
    assert 'Saisir une nouvelle réponse' in TEXT
    assert 'Corriger ma réponse actuelle' in TEXT
    assert 'Reformulation Clarté360' in TEXT

def test_no_false_reformulation_and_no_premature_official_fallback():
    tree=ast.parse(TEXT)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_official_answer_from_meta')
    body=ast.get_source_segment(TEXT,fn)
    assert 'transcription_corrigee' not in body
    assert 'version_officielle' in body
    assert 'AUCUNE_REFORMULATION' in TEXT
    assert 'already sufficiently clear' not in TEXT.lower()

def test_concept_nature_and_single_clarification_present():
    assert 'def analyse_concept_nature' in TEXT
    assert 'besoin, une peur, une émotion' in TEXT
    assert 'UNE seule question' in TEXT
    assert 'nature_decision' in TEXT

def test_report_is_central_list_only_and_old_sections_removed():
    start=TEXT.index('def create_pdf(')
    end=TEXT.index('\ndef display_header',start)
    pdf=TEXT[start:end]
    assert 'central_validated_values' in pdf
    assert 'Situations associées' not in pdf
    assert 'Émotions ou réactions' not in pdf
    assert 'Statut :</b> Validée' in pdf
    assert 'Boussole des valeurs professionnelles' in pdf
    assert 'Roue des valeurs' in pdf
