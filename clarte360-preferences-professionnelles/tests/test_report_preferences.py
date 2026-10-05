from pathlib import Path

import pandas as pd


def test_dimensions_reference_supports_detailed_report():
    df = pd.read_excel("data/questions_preferences_professionnelles_v1.xlsx", sheet_name="Dimensions")
    assert len(df) == 10
    assert set(df["Code"].astype(str).str.strip()) == {f"PP{i}" for i in range(1, 11)}
    for col in ["Dimension", "Question explorée", "Interprétation basse", "Interprétation haute"]:
        assert col in df.columns
        assert df[col].astype(str).str.strip().ne("").all()


def test_report_contains_detailed_screen_and_pdf_sections():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "def append_pdf_preference_details" in source
    assert 'story.append(Paragraph("Comprendre vos préférences professionnelles"' in source
    assert 'st.markdown("### Comprendre vos préférences professionnelles")' in source
    assert "Repères du continuum" in source
    assert "Pôle bas" in source
    assert "Pôle haut" in source


def test_graph_functions_are_preserved():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "def plot_bar_results" in source
    assert "def plot_radar_results" in source
    assert 'dpi=180' in source
    assert 'ax.set_ylim(0, 100)' in source
