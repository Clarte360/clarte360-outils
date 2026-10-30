from __future__ import annotations

from streamlit.testing.v1 import AppTest

from clarte360_cp.ui.research_resources import RESOURCE_GROUPS, render_research_resources


def _render_resources():
    from clarte360_cp.ui.research_resources import render_research_resources
    render_research_resources()


def test_beneficiary_resources_match_the_project_reference_and_render_without_api():
    expected = {
        "https://candidat.francetravail.fr/metierscope/",
        "https://www.onisep.fr/recherche/metiers",
        "https://candidat.francetravail.fr/rechercheoffre/emploi",
        "https://dataemploi.francetravail.fr/emploi/accueil",
        "https://labonneboite.francetravail.fr/",
        "https://www.intercariforef.org/outils/recherche-offreinfo",
        "https://www.intercariforef.org/outils/recherche-certifinfo",
        "https://www.francecompetences.fr/recherche-resultats/",
        "https://www.intercariforef.org/outils/recherche-quiforme",
        "https://catalogue-apprentissage.intercariforef.org/recherche/formations",
    }
    actual = {resource.url for _group, resources in RESOURCE_GROUPS for resource in resources}

    assert actual == expected
    assert all(resource.name and resource.purpose for _, resources in RESOURCE_GROUPS for resource in resources)

    app = AppTest.from_function(_render_resources, default_timeout=10).run()

    assert not app.exception and not app.error
    assert {button.url for button in app.link_button} == expected
    assert any("que les API soient disponibles ou non" in caption.value for caption in app.caption)
