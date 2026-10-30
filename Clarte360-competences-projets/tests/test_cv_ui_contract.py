from pathlib import Path


def test_cv_enrichment_remains_manual_reference_based_and_human_reviewed():
    source = (Path(__file__).parents[1] / "clarte360_cp/ui/accompagnateur.py").read_text(encoding="utf-8")
    assert 'link.purpose == "CV_SOURCE"' in source
    assert "gda.get_source(document.source_ref)" in source
    assert 'add_session_experience(ctx, case_id' in source
    assert "source_ref=document.source_ref" in source
    assert "Aucun niveau n’a été déduit" in source
    assert "aucune carte n’est créée avant votre action" in source.lower()
    assert "_render_cv_enrichment_after_cav3(ctx, case_id or \"\")" in source
    workspace = source.split("def _render_gda_document_workspace", 1)[1].split("def _render_cv_enrichment_after_cav3", 1)[0]
    assert "analyze_cv_text" not in workspace
    assert "cav3_analysis_history(ctx, case_id)" in source
    assert "disabled=not consented" in source
    assert "au bénéficiaire et il accepte" in source
