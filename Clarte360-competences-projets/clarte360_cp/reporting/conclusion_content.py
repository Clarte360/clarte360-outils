"""Shared, source-faithful section builders for final conclusion documents."""
from __future__ import annotations


def action_plan_sections(plan: dict) -> list[tuple[str, str]]:
    sections = []
    for index, item in enumerate(plan.get("items", ()), start=1):
        fields = [str(item.get("action") or "")]
        if item.get("due"):
            fields.append(f"Échéance : {item['due']}")
        if item.get("means"):
            fields.append(f"Moyens : {item['means']}")
        if item.get("expected"):
            fields.append(f"Résultat attendu : {item['expected']}")
        sections.append((f"Étape {index}", "\n".join(fields)))
    return sections


def results_sections(record: dict) -> list[tuple[str, str]]:
    labels = (
        ("parcours", "Parcours et éléments déterminants"),
        ("savoirs", "Savoirs et compétences mobilisables"),
        ("projet", "Projet étudié et raisons"),
        ("conditions", "Conditions de réalisation"),
        ("vigilances", "Points de vigilance et vérifications"),
        ("formations", "Formations ou certifications envisagées"),
        ("diploma_status", "Diplôme ou titre obligatoire, le cas échéant"),
        ("diploma_source", "Source officielle et date"),
    )
    content = record.get("content") or {}
    return [(label, str(content.get(key) or "Non renseigné")) for key, label in labels]


def synthesis_sections(record: dict) -> list[tuple[str, str]]:
    labels = (("objectif", "Objectif du bilan"), ("projet", "Projet professionnel retenu"),
              ("conditions", "Conditions et moyens de réalisation"), ("plan", "Plan d’action convenu"),
              ("suite", "Perspectives et points à reprendre"))
    content = record.get("content") or {}
    return [(label, str(content.get(key) or "Non renseigné")) for key, label in labels]
