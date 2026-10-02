from __future__ import annotations

from collections.abc import Iterable
from html import escape
from typing import Any

import streamlit as st


from clarte360_ipip.ui.results_model import facets_by_domain, professional_context, scale_position


def _scale_html(value: float, label: str) -> str:
    pos = scale_position(value)
    return (
        f'<div class="clarte-result-scale" role="img" aria-label="{escape(label)} : repère descriptif {pos:.0f} sur 100">'
        '<div class="clarte-result-track">'
        f'<span class="clarte-result-marker" style="left:{pos:.2f}%"></span>'
        '</div>'
        '<div class="clarte-result-axis"><span>moins marquée</span><span>zone intermédiaire</span><span>plus marquée</span></div>'
        '</div>'
    )


def render_results(interpretation: dict[str, Any]) -> None:
    """Render the J4 beneficiary restitution without changing interpretation/scoring."""
    st.success("Votre profil est calculé. Il décrit des tendances de fonctionnement, pas des catégories ni un diagnostic.")
    st.markdown(
        '<div class="clarte-hero"><b>Lire ces résultats comme des repères de réflexion</b><br/>'
        "Aucune dimension n'est meilleure qu'une autre. Une tendance peut être utile dans certains contextes et demander de la vigilance dans d'autres. "
        "Les résultats prennent leur sens lorsqu'ils sont rapprochés de situations réellement vécues.</div>",
        unsafe_allow_html=True,
    )

    st.header("Vue d'ensemble — 5 grandes dimensions")
    st.caption("Le repère 0–100 facilite uniquement la lecture visuelle. Il ne s'agit ni d'un percentile, ni d'une norme française, ni d'un classement.")
    for domain in interpretation.get("domains", []):
        st.markdown(f"### {domain['display_fr']}")
        st.markdown(_scale_html(domain["index_0_100"], domain["display_fr"]), unsafe_allow_html=True)
        st.markdown(f"**{domain['tendency_label']}**")
        st.write(domain["plain_definition"])
        st.caption(f"Terme scientifique : {domain['scientific_term']}")

    st.header("Explorer les 30 facettes")
    st.write("Chaque dimension se précise à travers six facettes. Ouvrez une dimension pour examiner les nuances qui la composent.")
    for domain in interpretation.get("domains", []):
        domain_facets = facets_by_domain(interpretation, domain["code"])
        with st.expander(f"{domain['display_fr']} — 6 facettes", expanded=False):
            for facet in domain_facets:
                st.markdown('<div class="clarte-facet-card">', unsafe_allow_html=True)
                st.markdown(f"#### {facet['display_fr']}")
                st.markdown(_scale_html(facet["index_0_100"], facet["display_fr"]), unsafe_allow_html=True)
                st.markdown(f"**{facet['tendency_label']}** — {facet['tendency_text']}")
                st.write(facet["plain_definition"])
                st.markdown(f"**Question à explorer :** {facet['debrief_question']}")
                st.caption(facet["guardrail"])
                st.markdown('</div>', unsafe_allow_html=True)

    st.header("Points d'appui et points de vigilance : à contextualiser")
    st.markdown(
        '<div class="clarte-box"><b>Un même trait peut jouer différemment selon la situation.</b><br/>'
        "Plutôt que de transformer un score en qualité ou en défaut, recherchez les situations où votre manière de fonctionner vous aide, "
        "puis celles où elle peut vous demander davantage d'attention ou d'ajustement.</div>",
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    with left:
        st.markdown("#### Points d'appui possibles")
        st.write("• Dans quelles situations cette tendance vous aide-t-elle à agir efficacement ?\n\n• Qu'est-ce qu'elle facilite dans vos relations, vos décisions ou votre organisation ?\n\n• Qu'aimeriez-vous continuer à mobiliser ?")
    with right:
        st.markdown("#### Points de vigilance possibles")
        st.write("• Dans quels contextes cette même tendance devient-elle moins adaptée ?\n\n• Que se passe-t-il lorsqu'elle est trop ou pas assez mobilisée ?\n\n• Quel ajustement pourrait vous donner davantage de choix ?")

    st.header("Exemples professionnels non prescriptifs")
    st.caption("Ces exemples servent uniquement à faire émerger des situations à discuter. Ils ne constituent ni une recommandation de métier ni une conclusion sur votre aptitude.")
    for domain in interpretation.get("domains", []):
        st.markdown(f"**{domain['display_fr']}** : observez comment cette tendance se manifeste {professional_context(domain['code'])}.")

    st.header("Questions de réflexion")
    questions: list[str] = []
    for domain in interpretation.get("domains", []):
        facets = facets_by_domain(interpretation, domain["code"])
        if facets:
            # One validated debrief question per domain keeps the page useful without overwhelming it.
            questions.append(facets[0]["debrief_question"])
    for question in questions:
        st.markdown(f"- {question}")

    st.header("À mettre en perspective avec mon parcours")
    st.write(
        "Ces résultats gagnent à être croisés avec vos expériences, vos valeurs, vos moteurs, vos préférences, votre RIASEC, "
        "vos compétences et votre projet. Cherchez ce qui vous ressemble, ce qui vous surprend, ce que vous souhaitez nuancer "
        "et les situations concrètes qui confirment ou contredisent ces repères."
    )
    st.info(interpretation["non_normative_notice"])
