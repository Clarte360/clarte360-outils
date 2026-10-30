"""GO22 - Contrat métier d'entrée : expression libre et relecture accompagnée.

Ce contrat ne mesure aucune compatibilité métier. Le bénéficiaire reste décideur.
Les sources APS/entreprise sont distinctes ; aucune ingestion automatique n'est supposée.
"""
from __future__ import annotations

import copy
from uuid import uuid4

MOTORS = (
    "Accomplir", "Comprendre", "Construire", "Transmettre", "Être utile",
    "Influencer", "Innover", "Coopérer", "Progresser", "Contribuer",
)
PREFERENCES = (
    "Autonomie", "Organisation", "Relations", "Décision", "Action",
    "Changement", "Environnement", "Apprentissage", "Contribution", "Responsabilités",
)
RIASEC = (
    "Réaliste", "Investigateur", "Artistique", "Social", "Entreprenant", "Conventionnel",
)
TOOLS = (
    ("BOUSSOLE_VALEURS", "Boussole", "Mes valeurs importantes pour mon futur travail"),
    ("MOTEURS_PRO", "Moteurs", "Ce qui me donne envie d'agir"),
    ("PREFERENCES_PRO", "Préférences", "Les conditions de travail recherchées ou évitées"),
    ("IPIP_REPORT", "IPIP-NEO-120", "Mes conditions de réussite, reconnues ou nuancées"),
    ("PIP_REPORT", "PIP RIASEC", "Les activités et univers qui m'attirent"),
)
IDEA_ORIGINS = {
    "EXPRESSION_SEANCE": "Expression en séance",
    "APS_BENEFICIAIRE": "Idée de l’APS bénéficiaire (report manuel à vérifier)",
    "APRES_RELECTURE": "Idée apparue lors de la relecture",
    "PARCOURS_CV": "Idée apparue en étudiant le parcours",
}
DECISIONS = ("A_DECIDER", "A_EXPLORER", "A_REFORMULER", "PLUS_AUJOURDHUI", "JE_NE_SAIS_PAS")
ENTERPRISE_CHOICES = ("NON_CONCERNE", "A_DECIDER", "A_CLARIFIER", "SOUHAITE_EXPLORER", "NE_SOUHAITE_PAS", "JE_NE_SAIS_PAS")
DIRECTION_ORIGINS = ("BENEFICIAIRE", "ECHANGE_ACCOMPAGNE")


def blank_orientation() -> dict:
    return {
        "schema": "GO22_ORIENTATION_V1",
        "ideas": [],
        "no_idea_yet": False,
        "enterprise": {
            "present": False, "wording": "", "source_label": "", "choice": "NON_CONCERNE",
        },
        "reviews": {
            code: {"source_note": "", "retained": [], "avoided": [], "reflection": ""}
            for code, _, _ in TOOLS
        },
        "directions": [],
    }


def _short(value: object, name: str, limit: int = 1500) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} doit être du texte.")
    clean = value.strip()
    if len(clean) > limit:
        raise ValueError(f"{name} dépasse {limit} caractères.")
    return clean


def _strings(values: object, name: str, *, max_items: int = 30) -> list[str]:
    if not isinstance(values, list) or len(values) > max_items:
        raise ValueError(f"{name} doit être une liste limitée à {max_items} éléments.")
    result = []
    for item in values:
        val = _short(item, name, 160)
        if val and val.casefold() not in {x.casefold() for x in result}:
            result.append(val)
    return result


def valid_orientation(payload: dict) -> dict:
    """Validation côté serveur, rejet des champs inconnus et des contenus excessifs."""
    if not isinstance(payload, dict) or payload.get("schema") != "GO22_ORIENTATION_V1":
        raise ValueError("Format d'orientation non reconnu.")
    expected = set(blank_orientation())
    if set(payload) != expected:
        raise ValueError("Structure d'orientation inattendue.")
    if not isinstance(payload["no_idea_yet"], bool):
        raise ValueError("La réponse 'pas encore d'idée' doit être explicite.")
    raw_ideas = payload["ideas"]
    if not isinstance(raw_ideas, list) or len(raw_ideas) > 100:
        raise ValueError("Nombre d'idées invalide.")
    ideas = []
    seen = set()
    for idea in raw_ideas:
        if not isinstance(idea, dict) or set(idea) != {"id", "original", "current", "origin", "decision"}:
            raise ValueError("Idée structurée invalide.")
        key = _short(idea["id"], "Identifiant idée", 40)
        if not key or key in seen:
            raise ValueError("Identifiant idée absent ou dupliqué.")
        seen.add(key)
        origin = _short(idea["origin"], "Origine", 40)
        decision = _short(idea["decision"], "Décision", 40)
        if origin not in IDEA_ORIGINS or decision not in DECISIONS:
            raise ValueError("Origine ou décision non reconnue.")
        orig = _short(idea["original"], "Expression originale", 500)
        current = _short(idea["current"], "Expression actuelle", 500)
        if not orig or not current:
            raise ValueError("Une idée ne peut pas être vide.")
        ideas.append({"id": key, "original": orig, "current": current, "origin": origin, "decision": decision})
    enterprise = payload["enterprise"]
    if not isinstance(enterprise, dict) or set(enterprise) != {"present", "wording", "source_label", "choice"}:
        raise ValueError("Bloc entreprise invalide.")
    if not isinstance(enterprise["present"], bool):
        raise ValueError("Présence entreprise invalide.")
    choice = _short(enterprise["choice"], "Choix entreprise", 40)
    if choice not in ENTERPRISE_CHOICES:
        raise ValueError("Choix de la perspective entreprise invalide.")
    employer_wording = _short(enterprise["wording"], "Perspective entreprise", 1000)
    source_label = _short(enterprise["source_label"], "Provenance entreprise", 200)
    if enterprise["present"] and (not employer_wording or not source_label or choice == "NON_CONCERNE"):
        raise ValueError("La perspective entreprise nécessite un énoncé, une provenance et un choix libre.")
    if not enterprise["present"] and (employer_wording or source_label or choice != "NON_CONCERNE"):
        raise ValueError("Une perspective entreprise non concernée doit rester vide.")
    revs = payload["reviews"]
    if not isinstance(revs, dict) or set(revs) != {c for c, _, _ in TOOLS}:
        raise ValueError("Relecture des cinq outils incomplète ou inattendue.")
    reviews = {}
    for code, _, _ in TOOLS:
        val = revs[code]
        if not isinstance(val, dict) or set(val) != {"source_note", "retained", "avoided", "reflection"}:
            raise ValueError("Relecture structurée invalide.")
        retain = _strings(val["retained"], f"Éléments retenus {code}")
        avoid = _strings(val["avoided"], f"Éléments à éviter {code}")
        if code == "BOUSSOLE_VALEURS" and len(retain) > 3:
            raise ValueError("La Boussole demande au plus trois valeurs choisies par le bénéficiaire.")
        if code == "MOTEURS_PRO" and any(x not in MOTORS for x in retain):
            raise ValueError("Moteur inconnu : retrouver les dix moteurs professionnels.")
        if code == "PREFERENCES_PRO" and any(x not in PREFERENCES for x in retain + avoid):
            raise ValueError("Dimension de préférence non reconnue.")
        if code == "PIP_REPORT" and any(x not in RIASEC for x in retain + avoid):
            raise ValueError("Dimension RIASEC non reconnue.")
        reviews[code] = {
            "source_note": _short(val["source_note"], f"Lecture de source {code}", 2000),
            "retained": retain,
            "avoided": avoid,
            "reflection": _short(val["reflection"], f"Réflexion {code}", 1200),
        }
    raw_directions = payload["directions"]
    if not isinstance(raw_directions, list) or len(raw_directions) > 100:
        raise ValueError("Nombre de directions invalide.")
    directions = []
    ids = set()
    for direction in raw_directions:
        if not isinstance(direction, dict) or set(direction) != {"id", "wording", "origin", "decision", "reason"}:
            raise ValueError("Direction structurée invalide.")
        key = _short(direction["id"], "Identifiant direction", 40)
        if not key or key in ids:
            raise ValueError("Direction dupliquée.")
        ids.add(key)
        origin = _short(direction["origin"], "Origine direction", 40)
        decision = _short(direction["decision"], "Choix direction", 40)
        if origin not in DIRECTION_ORIGINS or decision not in DECISIONS:
            raise ValueError("Origine/décision direction invalide.")
        wording = _short(direction["wording"], "Direction", 500)
        if not wording:
            raise ValueError("Une direction ne peut pas être vide.")
        directions.append({
            "id": key, "wording": wording, "origin": origin,
            "decision": decision, "reason": _short(direction["reason"], "Raison", 1000),
        })
    return {
        "schema": "GO22_ORIENTATION_V1", "ideas": ideas,
        "no_idea_yet": payload["no_idea_yet"],
        "enterprise": {"present": enterprise["present"], "wording": employer_wording, "source_label": source_label, "choice": choice},
        "reviews": reviews, "directions": directions,
    }


def new_idea(wording: str, origin: str = "EXPRESSION_SEANCE") -> dict:
    clean = _short(wording, "Idée", 500)
    if not clean or origin not in IDEA_ORIGINS:
        raise ValueError("Idée ou provenance invalide.")
    return {"id": str(uuid4()), "original": clean, "current": clean, "origin": origin, "decision": "A_DECIDER"}


def new_direction(wording: str, reason: str = "", origin: str = "BENEFICIAIRE") -> dict:
    clean = _short(wording, "Direction", 500)
    if not clean or origin not in DIRECTION_ORIGINS:
        raise ValueError("Direction invalide.")
    return {"id": str(uuid4()), "wording": clean, "reason": _short(reason, "Raison", 1000), "origin": origin, "decision": "A_DECIDER"}


def clone_orientation(document: dict) -> dict:
    return copy.deepcopy(document)
