"""GO22 RC2 - Questions C-AV1/C-AV2 neutres, sans aucun appel IA.

Les sources sont des REFERENCES d'artefacts existants (Hub/GDA) et des libelles
metier prepares/controles par l'accompagnateur. Rien n'est tire du CV avant C0.
Les choix de l'utilisateur ne sont jamais construits a partir d'un score.
"""
from __future__ import annotations

import copy
import hashlib
import json

from clarte360_cp.domain.orientation import MOTORS

SCHEMA_Q = "GO22_PREPARATION_QUESTIONNAIRE_V1"
SCHEMA_R = "GO22_PREPARATION_REPONSES_V1"

SOURCES = (
    "CV_SOURCE", "APS_OBJECTIF", "APS_P1", "BOUSSOLE_VALEURS", "MOTEURS_PRO",
    "PREFERENCES_PRO", "IPIP_REPORT", "PIP_REPORT", "ENTREPRISE_PERSPECTIVE",
)
CAV1_MEANINGS = (
    "Exercer ce métier", "Exercer une partie de ses activités", "Travailler dans ce secteur",
    "Rejoindre une organisation précise", "Explorer une opportunité", "Je souhaite préciser",
)
CAV1_STATUSES = (
    "Salariat privé", "Fonction publique", "Indépendant / libéral",
    "Entreprise familiale", "Création ou reprise", "Plusieurs cadres possibles", "Pas encore défini",
)
CAV1_ATTRACTIONS = (
    "Activités concrètes", "Environnement de travail", "Créativité ou innovation",
    "Responsabilités et autonomie", "Stabilité", "Opportunité précise", "Autre attrait",
)
CAV1_ACCESS = (
    "J'ai échangé avec des professionnels", "Je connais les qualifications requises",
    "J'ai vérifié les conditions d'exercice", "Une opportunité concrète existe",
    "Reste à vérifier", "Je n'ai pas encore approfondi",
)
SECTIONS = (
    ("VALEURS", "BOUSSOLE_VALEURS", "Mes valeurs indispensables", 3, True,
     "Quelles valeurs souhaitez-vous absolument pouvoir vivre dans votre futur travail ? (3 maximum)"),
    ("MOTEURS_ESSENTIELS", "MOTEURS_PRO", "Mes moteurs essentiels", 3, True,
     "Quels moteurs avez-vous besoin de mobiliser régulièrement pour conserver votre motivation ? (3 maximum)"),
    ("MOTEURS_PLUS", "MOTEURS_PRO", "Mes moteurs appréciables", 2, False,
     "Quels autres moteurs seraient appréciables sans être indispensables ? (2 maximum)"),
    ("PREF_GO", "PREFERENCES_PRO", "Conditions de travail indispensables", 3, True,
     "Quelles conditions concrètes de travail souhaitez-vous préserver ? (3 maximum)"),
    ("PREF_NO_GO", "PREFERENCES_PRO", "Situations que je souhaite éviter", 3, True,
     "Quelles situations concrètes ne souhaitez-vous pas retrouver ? (3 maximum)"),
    ("IPIP_FAVORISER", "IPIP_REPORT", "Conditions de fonctionnement à favoriser", 2, False,
     "Quelles conditions de fonctionnement personnel souhaitez-vous favoriser ? (2 maximum)"),
    ("IPIP_VIGILANCE", "IPIP_REPORT", "Points de vigilance éventuels", 2, False,
     "Quels points méritent de l'attention, selon votre ressenti ? (2 maximum)"),
    ("PIP_ATTRACTION", "PIP_REPORT", "Activités qui m'attirent", 5, False,
     "Quelles activités avez-vous envie d'explorer ou de pratiquer ? (5 maximum)"),
    ("PIP_EVITER", "PIP_REPORT", "Activités que je préfère éviter", 3, False,
     "Quelles activités préférez-vous ne pas pratiquer régulièrement ? (3 maximum)"),
)
SECTION_SPECS = {item[0]: item for item in SECTIONS}
NONE_REASONS = ("AUCUN_CRITERE_IDENTIFIE", "A_AFFINER")
CONTEXTS = ("AUTOFINANCE", "ENTREPRISE_TRIPARTITE", "ENTREPRISE_TRIPARTITE_MIXTE", "FINANCEMENT_MIXTE", "AUTRE")
ENTERPRISE_CONTEXTS = {"ENTREPRISE_TRIPARTITE", "ENTREPRISE_TRIPARTITE_MIXTE"}
ENTERPRISE_RESPONSES = (
    "NE_SOUHAITE_PAS", "SOUHAITE_EXPLORER", "SOUHAITE_CLARIFIER", "NE_SAIS_PAS",
)


def _text(value: object, field: str, maximum: int = 900, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} : texte attendu.")
    result = value.strip()
    if len(result) > maximum or (required and not result):
        raise ValueError(f"{field} : longueur ou contenu invalide.")
    return result


def _items(values: object, field: str, limit: int = 100, width: int = 180) -> list[str]:
    if not isinstance(values, list) or len(values) > limit:
        raise ValueError(f"{field} : liste incorrecte.")
    cleaned: list[str] = []
    for item in values:
        v = _text(item, field, width, required=True)
        if v.casefold() not in {p.casefold() for p in cleaned}:
            cleaned.append(v)
    return cleaned


def fingerprint(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _source_items(code: str, source: dict) -> list[str]:
    if code == "MOTEURS_PRO":
        return list(MOTORS)
    return _items(source.get("items", []), f"Items {code}", limit=100)


def generate_questionnaire(sources: dict, *, context: str = "AUTRE", intro: str = "") -> dict:
    """Tronc fixe + listes references ; ne fait PAS d'inference IA ni lecture de CV."""
    if context not in CONTEXTS:
        raise ValueError("Contexte contractuel non reconnu.")
    if not isinstance(sources, dict) or set(sources) - set(SOURCES):
        raise ValueError("Références de sources non reconnues.")
    source_refs: list[dict] = []
    normalized: dict[str, dict] = {}
    for code in SOURCES:
        raw = sources.get(code)
        if raw is None:
            continue
        if not isinstance(raw, dict) or not raw.get("authorized", False):
            # Une perspective entreprise non autorisee reste completement absente.
            continue
        ref = _text(raw.get("source_ref", ""), f"Référence {code}", 240, required=True)
        label = _text(raw.get("label", code), f"Libellé {code}", 160)
        items = _source_items(code, raw)
        data = {"code": code, "source_ref": ref, "label": label,
                "items": items, "date": _text(raw.get("date", ""), "Date", 50)}
        if code == "PREFERENCES_PRO":
            # Les conditions recherchees et les situations a eviter ne sont
            # pas automatiquement la meme liste. Chaque pole est explicite.
            data["items_go"] = _items(raw.get("items_go", items), "Pôles GO Préférences", 100)
            data["items_no_go"] = _items(raw.get("items_no_go", items), "Pôles NO GO Préférences", 100)
        if code in {"APS_OBJECTIF", "APS_P1"}:
            data["idea_list"] = _items(raw.get("idea_list", []), "Idées APS", 50, 300)
        if code == "ENTREPRISE_PERSPECTIVE":
            if context not in ENTERPRISE_CONTEXTS:
                raise ValueError("Une perspective employeur ne vaut pas un contexte tripartite autorisé.")
            data["wording"] = _text(raw.get("wording", ""), "Perspective employeur", 800, required=True)
        normalized[code] = data
        # Pas de PDF ni de reponses de test dans le questionnaire.
        source_refs.append({"code": code, "source_ref": ref, "label": label, "date": data["date"]})
    ideas: list[str] = []
    for code in ("APS_OBJECTIF", "APS_P1"):
        for wording in normalized.get(code, {}).get("idea_list", []):
            if wording.casefold() not in {x.casefold() for x in ideas}:
                ideas.append(wording)
    sections: list[dict] = []
    for code, source_code, label, count, required, question in SECTIONS:
        src = normalized.get(source_code)
        if not src:
            continue
        values = (src["items_go"] if code == "PREF_GO" else
                  src["items_no_go"] if code == "PREF_NO_GO" else src["items"])
        if not values:
            continue
        sections.append({"code": code, "source_code": source_code,
                         "label": label, "question": question,
                         "choices": values, "max": count, "required": required})
    employer = normalized.get("ENTREPRISE_PERSPECTIVE")
    doc = {
        "schema": SCHEMA_Q, "context": context,
        "intro": _text(intro, "Introduction", 1400) or
                 "Ce questionnaire prépare notre prochain échange. Il n'existe aucune bonne réponse ; vos choix restent libres et nous pourrons les revoir ensemble.",
        "source_refs": source_refs, "aps_ideas": ideas,
        "enterprise_wording": employer["wording"] if employer else "",
        "sections": sections, "idea_questions": {
            "meaning": list(CAV1_MEANINGS), "status": list(CAV1_STATUSES),
            "attraction": list(CAV1_ATTRACTIONS), "access": list(CAV1_ACCESS),
        },
    }
    return valid_questionnaire(doc)


def valid_questionnaire(doc: dict) -> dict:
    expected = {"schema", "context", "intro", "source_refs", "aps_ideas", "enterprise_wording", "sections", "idea_questions"}
    if not isinstance(doc, dict) or set(doc) != expected or doc.get("schema") != SCHEMA_Q:
        raise ValueError("Structure du questionnaire invalide.")
    if doc["context"] not in CONTEXTS:
        raise ValueError("Contexte invalide.")
    result = copy.deepcopy(doc)
    result["intro"] = _text(doc["intro"], "Introduction", 1400, required=True)
    result["aps_ideas"] = _items(doc["aps_ideas"], "Idées APS", 50, 300)
    result["enterprise_wording"] = _text(doc["enterprise_wording"], "Perspective employeur", 800)
    if result["enterprise_wording"] and doc["context"] not in ENTERPRISE_CONTEXTS:
        raise ValueError("Perspective entreprise non autorisée.")
    if not isinstance(doc["source_refs"], list) or len(doc["source_refs"]) > len(SOURCES):
        raise ValueError("Nombre de sources incorrect.")
    refs: list[dict] = []
    seen_sources: set[str] = set()
    for r in doc["source_refs"]:
        if not isinstance(r, dict) or set(r) != {"code", "source_ref", "label", "date"}:
            raise ValueError("Référence de source invalide.")
        c = _text(r["code"], "Code source", 50)
        if c not in SOURCES or c in seen_sources:
            raise ValueError("Source dupliquée ou inconnue.")
        seen_sources.add(c)
        refs.append({"code": c, "source_ref": _text(r["source_ref"], c, 240, required=True),
                     "label": _text(r["label"], "Libellé", 160),
                     "date": _text(r["date"], "Date source", 50)})
    result["source_refs"] = refs
    if not isinstance(doc["idea_questions"], dict) or set(doc["idea_questions"]) != {"meaning", "status", "attraction", "access"}:
        raise ValueError("Rubriques de clarification des métiers invalides.")
    result["idea_questions"] = {key: _items(doc["idea_questions"][key], key, 20) for key in doc["idea_questions"]}
    if any(not result["idea_questions"][key] for key in result["idea_questions"]):
        raise ValueError("Une rubrique métier ne peut pas être supprimée.")
    if not isinstance(doc["sections"], list) or len(doc["sections"]) > len(SECTIONS):
        raise ValueError("Sections de questionnaire incorrectes.")
    seen: set[str] = set()
    validated = []
    for s in doc["sections"]:
        if not isinstance(s, dict) or set(s) != {"code", "source_code", "label", "question", "choices", "max", "required"}:
            raise ValueError("Section invalide.")
        key = _text(s["code"], "Code section", 50)
        if key not in SECTION_SPECS or key in seen:
            raise ValueError("Section dupliquée/inconnue.")
        seen.add(key)
        _, source_code, _, count, mandatory, _ = SECTION_SPECS[key]
        if s["source_code"] != source_code or source_code not in seen_sources or s["max"] != count or s["required"] != mandatory:
            raise ValueError("Source, maximum ou caractère obligatoire de section modifié.")
        choices = _items(s["choices"], f"Choix {key}")
        if not choices:
            raise ValueError("Une section ne peut être vide.")
        validated.append({"code": key, "source_code": source_code,
                          "label": _text(s["label"], "Titre", 160, required=True),
                          "question": _text(s["question"], "Question", 600, required=True),
                          "choices": choices, "max": count, "required": mandatory})
    result["sections"] = validated
    return result


def empty_answers(questionnaire: dict) -> dict:
    valid_questionnaire(questionnaire)
    # Les pistes APS sont des PROPOSITIONS a confirmer ; aucune ne doit etre
    # validee tacitement parce qu'elle figure dans un document precedent.
    # L'UI les propose a cocher sans ressaisie.
    return {"schema": SCHEMA_R, "no_idea_yet": False, "ideas": [],
            "enterprise_position": "NE_SAIS_PAS" if questionnaire["enterprise_wording"] else "NON_CONCERNE",
            "enterprise_note": "", "selections": {s["code"]: [] for s in questionnaire["sections"]},
            "none_reasons": {}, "observations": {}}


def valid_answers(doc: dict, questionnaire: dict, *, final: bool = False) -> dict:
    q = valid_questionnaire(questionnaire)
    keys = {"schema", "no_idea_yet", "ideas", "enterprise_position", "enterprise_note", "selections", "none_reasons", "observations"}
    if not isinstance(doc, dict) or set(doc) != keys or doc.get("schema") != SCHEMA_R:
        raise ValueError("Structure des réponses invalide.")
    result = copy.deepcopy(doc)
    if not isinstance(doc["no_idea_yet"], bool):
        raise ValueError("Le statut d'idée doit être explicite.")
    if not isinstance(doc["ideas"], list) or len(doc["ideas"]) > 50:
        raise ValueError("Nombre d'idées invalide.")
    ideas = []
    for idx, idea in enumerate(doc["ideas"]):
        if not isinstance(idea, dict) or set(idea) != {"wording", "meaning", "status", "attraction", "access", "note"}:
            raise ValueError("Fiche idée incorrecte.")
        clean = {"wording": _text(idea["wording"], "Métier/activité", 300, required=True),
                 "note": _text(idea["note"], "Observation idée", 1500)}
        for key in ("meaning", "status", "attraction", "access"):
            selected = _items(idea[key], key, 20)
            if set(selected) - set(q["idea_questions"][key]):
                raise ValueError("Une réponse métier n'appartient pas au questionnaire validé.")
            clean[key] = selected
        ideas.append(clean)
    if ideas and doc["no_idea_yet"]:
        raise ValueError("Une idée exprimée et 'aucune idée' ne peuvent être cochées simultanément.")
    result["ideas"] = ideas
    if final and not ideas and not doc["no_idea_yet"]:
        raise ValueError("Indiquez au moins une idée ou confirmez n'en avoir aucune à ce stade.")
    selected_position = _text(doc["enterprise_position"], "Position entreprise", 40)
    if q["enterprise_wording"]:
        if selected_position not in ENTERPRISE_RESPONSES:
            raise ValueError("Position entreprise inconnue.")
    elif selected_position != "NON_CONCERNE":
        raise ValueError("Bloc entreprise non autorisé dans ce dossier.")
    result["enterprise_position"] = selected_position
    result["enterprise_note"] = _text(doc["enterprise_note"], "Précisions entreprise", 1500)
    allowed_sections = {s["code"]: s for s in q["sections"]}
    if not isinstance(doc["selections"], dict) or set(doc["selections"]) != set(allowed_sections):
        raise ValueError("Sélections incohérentes avec le questionnaire figé.")
    if not isinstance(doc["none_reasons"], dict) or set(doc["none_reasons"]) - set(allowed_sections):
        raise ValueError("Motifs non reconnus.")
    if not isinstance(doc["observations"], dict) or set(doc["observations"]) - set(allowed_sections):
        raise ValueError("Observations non reconnues.")
    selections: dict[str, list[str]] = {}
    for key, section in allowed_sections.items():
        values = _items(doc["selections"][key], key, 100)
        if len(values) > section["max"] or set(values) - set(section["choices"]):
            raise ValueError(f"{section['label']} : choix ou nombre invalide.")
        if key == "VALEURS" and len(values) > 3:
            raise ValueError("La limite est de trois valeurs.")
        selections[key] = values
        reason = doc["none_reasons"].get(key, "")
        if reason not in ("", *NONE_REASONS):
            raise ValueError("Motif de non-sélection invalide.")
        if values and reason:
            raise ValueError("Une sélection et un motif d'absence de sélection sont incompatibles.")
        if final and section["required"] and not values and reason not in NONE_REASONS:
            raise ValueError(f"{section['label']} : faites un choix ou précisez l'absence de priorité.")
    if set(selections.get("MOTEURS_ESSENTIELS", [])) & set(selections.get("MOTEURS_PLUS", [])):
        raise ValueError("Un même moteur ne peut pas être à la fois indispensable et seulement appréciable.")
    if set(selections.get("PREF_GO", [])) & set(selections.get("PREF_NO_GO", [])):
        raise ValueError("Une même condition ne peut pas être à rechercher et à éviter sans clarification.")
    result["selections"] = selections
    result["none_reasons"] = {k: v for k, v in doc["none_reasons"].items() if v}
    result["observations"] = {k: _text(v, "Observation", 1200) for k, v in doc["observations"].items()}
    return result


def difference(old: dict, new: dict) -> dict:
    return {key: {"avant": old.get(key), "apres": new.get(key)} for key in sorted(set(old) | set(new)) if old.get(key) != new.get(key)}

# RC3 - format additif versionne. Les documents RC2 et leurs snapshots ne
# changent pas; leurs validateurs historiques restent actifs par dispatch.
from clarte360_cp.domain.preparation_v2 import (  # noqa: E402
    SCHEMA_Q_V2, SCHEMA_R_V2, generate_questionnaire_v2,
    valid_questionnaire_v2, empty_answers_v2, valid_answers_v2,
    public_questionnaire_v2,
)

_legacy_valid_questionnaire = valid_questionnaire
_legacy_valid_answers = valid_answers
_legacy_empty_answers = empty_answers


def valid_questionnaire(doc: dict) -> dict:
    if isinstance(doc, dict) and doc.get('schema') == SCHEMA_Q_V2:
        return valid_questionnaire_v2(doc)
    return _legacy_valid_questionnaire(doc)


def empty_answers(questionnaire: dict) -> dict:
    if isinstance(questionnaire, dict) and questionnaire.get('schema') == SCHEMA_Q_V2:
        return empty_answers_v2(questionnaire)
    return _legacy_empty_answers(questionnaire)


def valid_answers(doc: dict, questionnaire: dict, *, final: bool = False) -> dict:
    if isinstance(questionnaire, dict) and questionnaire.get('schema') == SCHEMA_Q_V2:
        return valid_answers_v2(doc, questionnaire, final=final)
    return _legacy_valid_answers(doc, questionnaire, final=final)
