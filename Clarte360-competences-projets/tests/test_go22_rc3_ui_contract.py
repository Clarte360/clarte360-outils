"""GO22 RC3B : contrôle du parcours UI sans tester la taille des fichiers Python."""
from pathlib import Path
from clarte360_cp.domain.preparation_v2 import SCHEMA_Q_V2, SCHEMA_R_V2

ROOT=Path(__file__).parents[1]

def test_separate_ui_and_app_stage_code():
    ui=(ROOT/"clarte360_cp/ui/preparation_rc3.py").read_text(encoding="utf-8")
    fields=(ROOT/"clarte360_cp/ui/preparation_rc3b.py").read_text(encoding="utf-8")
    app=(ROOT/"clarte360_cp/application/preparation.py").read_text(encoding="utf-8")
    assert "Étape 1/2" in fields and "Étape 2/2" in fields
    assert "save_beneficiary_answers" in ui and "submit_beneficiary_answers" in ui
    assert 'st.session_state[step_key]=2' in ui
    assert 'if not previous or not _doc(previous).get("cav1_done")' in app
    assert "open_beneficiary_access" in ui
    assert "send_email" not in ui and "openai" not in ui.lower()
    # Les questions conditionnelles ne sont plus emprisonnées dans un st.form.
    assert "with st.form" not in fields
    assert "st.pills" in fields or "st.checkbox" in fields

def test_v2_documents_are_explicitly_distinct():
    assert SCHEMA_Q_V2!=SCHEMA_R_V2
    assert SCHEMA_Q_V2.endswith("_V2") and SCHEMA_R_V2.endswith("_V2")
