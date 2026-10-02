from __future__ import annotations
from typing import Any

PROFESSIONAL_CONTEXTS = {
    "N": "par exemple face à une échéance, un imprévu, une tension relationnelle ou une période de forte charge",
    "E": "par exemple dans les échanges, les réunions, la prise de parole, le travail collectif ou les temps de concentration",
    "O": "par exemple lorsqu'il faut explorer une idée, apprendre, imaginer une autre façon de faire ou travailler dans un cadre déjà établi",
    "A": "par exemple dans la coopération, la négociation, le désaccord, l'entraide ou la défense d'un point de vue",
    "C": "par exemple dans l'organisation, la préparation, le suivi, la tenue d'un engagement ou l'adaptation à une priorité nouvelle",
}

def facets_by_domain(interpretation: dict[str, Any], domain_code: str) -> list[dict[str, Any]]:
    return [x for x in interpretation.get("facets", []) if x.get("domain") == domain_code]

def scale_position(index_0_100: float) -> float:
    return max(0.0, min(100.0, float(index_0_100)))

def professional_context(domain_code: str) -> str:
    return PROFESSIONAL_CONTEXTS.get(domain_code, "par exemple dans une situation professionnelle concrète de votre parcours")
