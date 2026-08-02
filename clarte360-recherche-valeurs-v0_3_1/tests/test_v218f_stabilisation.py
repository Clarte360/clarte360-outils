from pathlib import Path
import importlib.util
import sys

APP=Path(__file__).resolve().parents[1]/'app.py'
TEXT=APP.read_text(encoding='utf-8')

def load_app():
    from test_v218_model import load_app as _load
    return _load()

def test_version_f_and_cross_module_language_rule():
    assert 'APP_VERSION = "2.1.3.9B-preproduction"' in TEXT
    assert 'Corrigez toujours les fautes d\'orthographe' in TEXT
    assert 'expected_value_label' in TEXT

def test_contextual_value_label_cleanup():
    mod, _ = load_app()
    # Injecte des valeurs de test indépendamment du contenu exact du classeur livré.
    mod.VALUE_NAMES = list(dict.fromkeys(list(mod.VALUE_NAMES)+['Optimisme','Perfectionnisme']))
    mod.VALUE_MAP.setdefault('Optimisme', {'nom':'Optimisme','definition':''})
    assert mod._clean_value_label_input("L'optimisme, je répète, l'optimisme.") == 'Optimisme'
    assert mod._clean_value_label_input('Loopisme') == 'Optimisme'

def test_pdf_pagination_guards_present():
    assert 'CondPageBreak(4.2*cm)' in TEXT
    assert 'keepWithNext=True' in TEXT
