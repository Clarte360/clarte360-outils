"""Direct external resources for beneficiary-led career investigations.

These links remain available regardless of France Travail API access or uptime.
They support investigations assigned by the accompanist; beneficiaries are not
expected to consult every resource for every project.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchResource:
    name: str
    url: str
    purpose: str


RESOURCE_GROUPS: tuple[tuple[str, tuple[ResearchResource, ...]], ...] = (
    (
        "Explorer les métiers et les offres",
        (
            ResearchResource(
                "MétierScope — France Travail",
                "https://candidat.francetravail.fr/metierscope/",
                "Découvrir les activités, compétences et conditions d'accès d'un métier.",
            ),
            ResearchResource(
                "Métiers — Onisep",
                "https://www.onisep.fr/recherche/metiers",
                "Explorer des métiers et les parcours de formation associés.",
            ),
            ResearchResource(
                "Offres d'emploi — France Travail",
                "https://candidat.francetravail.fr/rechercheoffre/emploi",
                "Comparer les missions, compétences demandées, lieux et contrats.",
            ),
        ),
    ),
    (
        "Examiner le territoire et les entreprises",
        (
            ResearchResource(
                "Data Emploi — France Travail",
                "https://dataemploi.francetravail.fr/emploi/accueil",
                "Observer l'emploi et les recrutements sur un territoire.",
            ),
            ResearchResource(
                "La Bonne Boîte — France Travail",
                "https://labonneboite.francetravail.fr/",
                "Repérer des entreprises à contacter pour une enquête ou une candidature.",
            ),
        ),
    ),
    (
        "Rechercher une formation ou vérifier une certification",
        (
            ResearchResource(
                "Offre Info — Réseau des Carif-Oref",
                "https://www.intercariforef.org/outils/recherche-offreinfo",
                "Rechercher une formation, puis vérifier dates, modalités et accès.",
            ),
            ResearchResource(
                "Certif Info — Réseau des Carif-Oref",
                "https://www.intercariforef.org/outils/recherche-certifinfo",
                "Identifier une certification et ses correspondances officielles.",
            ),
            ResearchResource(
                "France compétences — RNCP et Répertoire spécifique",
                "https://www.francecompetences.fr/recherche-resultats/",
                "Vérifier le code, le statut et la validité d'une certification.",
            ),
            ResearchResource(
                "QuiForme — Réseau des Carif-Oref",
                "https://www.intercariforef.org/outils/recherche-quiforme",
                "Rechercher un organisme de formation selon le besoin.",
            ),
            ResearchResource(
                "Catalogue de l'apprentissage",
                "https://catalogue-apprentissage.intercariforef.org/recherche/formations",
                "Repérer des formations et établissements pour un projet en apprentissage.",
            ),
        ),
    ),
)


def render_research_resources(*, groups: tuple[str, ...] | None = None) -> None:
    """Render curated links in the beneficiary workspace, without API dependency."""
    import streamlit as st

    selected = [
        (title, resources)
        for title, resources in RESOURCE_GROUPS
        if groups is None or title in groups
    ]
    st.markdown("### Ressources externes pour mes investigations")
    st.caption(
        "Ces recherches complètent le travail avec votre accompagnateur et restent accessibles "
        "que les API soient disponibles ou non. Consultez seulement les ressources utiles à "
        "l'action qui vous a été confiée."
    )
    for title, resources in selected:
        with st.expander(title, expanded=len(selected) == 1):
            cols = st.columns(2)
            for index, resource in enumerate(resources):
                with cols[index % 2]:
                    st.link_button(resource.name, resource.url, use_container_width=True)
                    st.caption(resource.purpose)
    st.info(
        "Après votre recherche, notez la source et la date, ce que vous avez appris, "
        "et ce que cela change ou confirme dans votre projet."
    )
