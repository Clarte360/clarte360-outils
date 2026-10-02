from pathlib import Path

from clarte360_ipip.interpretation import interpret_scoring, load_interpretation
from clarte360_ipip.questionnaire import load_questionnaire
from clarte360_ipip.scoring import score_questionnaire
from clarte360_ipip.ui.results_model import facets_by_domain, professional_context, scale_position

BASE = Path(__file__).resolve().parents[1]


def _interpretation():
    q = load_questionnaire(BASE/'resources/ipip/REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json')
    ref = load_interpretation(BASE/'resources/ipip/REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json')
    return interpret_scoring(score_questionnaire(q,{i:3 for i in range(1,121)}),ref)


def test_j4_groups_six_facets_per_domain():
    out=_interpretation()
    assert len(out['domains']) == 5
    assert all(len(facets_by_domain(out,d['code'])) == 6 for d in out['domains'])


def test_j4_display_scale_is_bounded_and_non_scoring():
    assert scale_position(-2) == 0
    assert scale_position(42.5) == 42.5
    assert scale_position(104) == 100


def test_j4_has_professional_context_for_all_domains():
    for code in 'NEOAC':
        assert 'par exemple' in professional_context(code)


def test_j4_app_delegates_results_to_structured_renderer():
    source=(BASE/'app.py').read_text(encoding='utf-8')
    assert 'render_results(interp)' in source
    results=(BASE/'clarte360_ipip/ui/results.py').read_text(encoding='utf-8')
    for required in [
        "Vue d'ensemble — 5 grandes dimensions",
        "Explorer les 30 facettes",
        "Points d'appui et points de vigilance",
        "Exemples professionnels non prescriptifs",
        "Questions de réflexion",
        "À mettre en perspective avec mon parcours",
    ]:
        assert required in results
    assert 'st.progress' not in results
    assert 'ni d’un percentile' not in results  # apostrophe form guard; explicit wording below is plain ASCII apostrophe
    assert "ni d'un percentile" in results
