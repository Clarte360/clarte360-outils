from pathlib import Path

PAGES = Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")

def test_h2_shows_report_before_feeling():
    assert "_render_pip_report_preview_before_feeling" in PAGES
    assert "J’ai consulté ma synthèse — donner mon ressenti" in PAGES
    assert "pdf_pages_as_png(pdf_bytes, 3, 4)" in PAGES

def test_h2_feeling_copy_confirms_prior_detailed_review():
    assert "Vous avez maintenant consulté une restitution détaillée de votre profil" in PAGES

def test_h2_keeps_public_report_version_unchanged():
    from clarte360_pip.reporting import PIP_REPORT_VERSION
    assert PIP_REPORT_VERSION == "PIP-RPT-1.6"
