"""Résultats entièrement SYNTHÉTIQUES, sans copie d'un dossier client.

Les données sont déclarées FICTIVES dans chacun des jeux de sources ; aucun
nombre ci-dessous n'est un résultat réel, et aucune inférence IA n'est faite.
"""
from __future__ import annotations

VALUE_DEFS = {
    "Créativité": "Pouvoir imaginer, concevoir et trouver de nouvelles façons de faire.",
    "Respect": "Être traité avec considération et traiter autrui de la même manière.",
    "Autonomie": "Disposer d'une marge de décision dans ses activités.",
    "Coopération": "Pouvoir construire et agir avec d'autres personnes.",
    "Utilité": "Percevoir à quoi son travail contribue concrètement.",
    "Sécurité": "Disposer de repères et d'une stabilité suffisante.",
}
MOTOR_DEFS = {
    "Accomplir": "Voir un projet aboutir et constater un résultat concret.",
    "Innover": "Essayer de nouvelles solutions et améliorer l'existant.",
    "Contribuer": "Participer à une finalité qui a du sens pour soi.",
    "Influencer": "Participer aux choix et faire évoluer des décisions.",
    "Comprendre": "Explorer des idées, analyser et relier des informations.",
    "Construire": "Donner forme et consistance à un projet.",
    "Transmettre": "Partager une expérience ou des connaissances.",
    "Progresser": "Apprendre et constater son évolution.",
    "Coopérer": "Travailler avec les autres et mutualiser les efforts.",
    "Être utile": "Rendre un service ou répondre à un besoin concret.",
}
RIASEC = [
    ("R", "Réaliste", "Activités concrètes, fabrication, terrain et techniques.", "72/100"),
    ("I", "Investigateur", "Observer, rechercher, analyser et résoudre des problèmes.", "46/100"),
    ("A", "Artistique", "Imaginer, créer, concevoir et exprimer des idées.", "54/100"),
    ("S", "Social", "Transmettre, conseiller, aider et accompagner.", "65/100"),
    ("E", "Entreprenant", "Entreprendre, convaincre, organiser une action collective.", "31/100"),
    ("C", "Conventionnel", "Structurer, suivre et fiabiliser l'information ou des opérations.", "60/100"),
]
NEO = [
    ("N", "Sensibilité émotionnelle", "Réactions aux émotions et aux situations stressantes.", "43/100"),
    ("E", "Énergie relationnelle", "Tendance à rechercher la présence d'autrui et l'activité.", "61/100"),
    ("O", "Ouverture à l’expérience", "Goût pour les idées, les expériences et les approches nouvelles.", "68/100"),
    ("A", "Coopération et considération des autres", "Manière de tenir compte des autres et de coopérer.", "58/100"),
    ("C", "Organisation et persévérance", "Façon d'organiser et de poursuivre les tâches.", "72/100"),
]


def row(key, label, explanation, score):
    return {"key": key, "label": label, "explanation": explanation, "score_display": score}


def make_summary(scale, rows, *, note="", profile_code=""):
    return {"scale": scale, "note": note, "rows": rows, "profile_code": profile_code}


def demo_summaries(values, motors, preference_dimensions):
    val_scores = ["6/10", "8/10", "7/10", "5/10", "6/10", "9/10"]
    motor_scores = ["63 %", "49 %", "57 %", "40 %", "68 %", "54 %", "46 %", "60 %", "51 %", "55 %"]
    pref_scores = ["65 %", "61 %", "70 %", "46 %", "58 %", "64 %", "53 %", "60 %", "73 %", "41 %"]
    return {
        "BOUSSOLE_VALEURS":make_summary(
            "Cotation d'incarnation sur 10 ; ce n'est pas une note d'importance pour l'avenir.",
            [row(name, name, VALUE_DEFS.get(name, "Définition à reprendre du rapport source."), val_scores[i % len(val_scores)]) for i,name in enumerate(values)],
            note="Ces notes sont des exemples inventés pour la recette. Vous choisissez librement vos valeurs essentielles."),
        "MOTEURS_PRO":make_summary(
            "Indices de motivation déclarée, en % selon le rapport Moteurs ; les indices ne décident pas des priorités.",
            [row(name,name,MOTOR_DEFS.get(name,"Définition du rapport source."),motor_scores[i % len(motor_scores)]) for i,name in enumerate(motors)],
            note="Les pourcentages de cette simulation ne proviennent d'aucune personne."),
        "PREFERENCES_PRO":make_summary(
            "Position en % sur le continuum du rapport, du pôle 1 vers le pôle 2 (ni aptitude, ni compétence).",
            [row(p["code"],p["label"],"Pôle 1 : "+p["pole_1"]+" / Pôle 2 : "+p["pole_2"], pref_scores[i % len(pref_scores)]) for i,p in enumerate(preference_dimensions)],
            note="Le pourcentage décrit une position entre deux façons de travailler, pas un degré de réussite."),
        "IPIP_REPORT":make_summary(
            "Repère descriptif sur 100 ; ni percentile ni norme psychométrique française.",
            [row(*r) for r in NEO],
            note="Exemples entièrement fictifs. Les dimensions sont des tendances continues, pas un diagnostic."),
        "PIP_REPORT":make_summary(
            "Indices d'intérêts sur 100 selon le PIP ; ce ne sont pas des aptitudes.",
            [row(*r) for r in RIASEC],
            note="Profil fictif pour apprendre à lire les six familles d'intérêts. Aucun métier n'en est automatiquement déduit.",
            profile_code="RSC"),
    }
