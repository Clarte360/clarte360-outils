"""Normalisation sûre des savoirs et compétences d'une fiche ROME 4.0."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RomeStudyItem:
    key: str
    label: str
    category: str
    hierarchy: str = ""


_CATEGORY_FIELDS = {
    "SAVOIR_FAIRE": ("savoir_faire", "savoirFaire", "savoirFaireProfessionnel", "savoir_faires"),
    "SAVOIR_ETRE": ("savoir_etre_professionnel", "savoirEtreProfessionnel", "savoirEtre", "savoir_etre"),
    "SAVOIR": ("savoirs", "savoir"),
}
_LABEL_FIELDS = ("libelle", "label", "intitule", "nom")
_CODE_FIELDS = ("code_ogr", "codeOgr", "code", "id", "cle")
_CONTAINERS = ("items", "item", "competences", "categories", "categorie", "enjeux", "enjeu",
               "objectifs", "macroCompetences", "macro_competences", "sousCategories", "sous_categories")


def _first(obj: Mapping[str, Any], names: tuple[str, ...]) -> str | None:
    for key in names:
        value = obj.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    return None


def _collect(node: Any, category: str, hierarchy: tuple[str, ...], out: list[RomeStudyItem]) -> None:
    if isinstance(node, list):
        for child in node:
            _collect(child, category, hierarchy, out)
        return
    if not isinstance(node, Mapping):
        return

    label = _first(node, _LABEL_FIELDS)
    code = _first(node, _CODE_FIELDS)
    # A ROME item has both a stable identifier and its displayed wording.
    # A hierarchy node may have a label but no OGR code, so it is never
    # offered for selection as though it were an expected skill.
    if label and code:
        out.append(RomeStudyItem(
            key=f"{category}:{code}", label=label, category=category,
            hierarchy=" › ".join((*hierarchy, label)) if hierarchy else "",
        ))
        return

    next_hierarchy = hierarchy + ((label,) if label else ())
    for key in _CONTAINERS:
        if key in node:
            _collect(node[key], category, next_hierarchy, out)


def rome_study_items(payload: Mapping[str, Any]) -> tuple[RomeStudyItem, ...]:
    """Extract selectable savoirs and competences from API/XML-shaped JSON.

    Does not inspect ``acces_metier`` or infer diploma requirements. Both the
    France Travail API and the supplied ROME XML use the same item concepts,
    although the API response still needs a live contract check.
    """
    root: Mapping[str, Any] = payload
    for wrapper in ("ficheMetier", "fiche_metier", "metier", "resultat"):
        nested = root.get(wrapper)
        if isinstance(nested, Mapping):
            root = nested
            break
    competencies = root.get("competences", root)
    if not isinstance(competencies, Mapping):
        return ()
    found: list[RomeStudyItem] = []
    for category, fields in _CATEGORY_FIELDS.items():
        value = next((competencies[field] for field in fields if field in competencies), None)
        if value is not None:
            _collect(value, category, (), found)
    # Also accept a flat API array if each row explicitly declares its nature.
    flat = competencies.get("items")
    if isinstance(flat, list):
        for item in flat:
            if not isinstance(item, Mapping):
                continue
            nature = str(item.get("nature") or item.get("type") or "").casefold().replace("-", "_")
            category = ("SAVOIR_FAIRE" if "faire" in nature else
                        "SAVOIR_ETRE" if "etre" in nature or "être" in nature else
                        "SAVOIR" if "savoir" in nature else None)
            if category:
                _collect(item, category, (), found)
    unique: dict[str, RomeStudyItem] = {}
    for item in found:
        unique.setdefault(item.key, item)
    return tuple(sorted(unique.values(), key=lambda item: (item.category, item.label.casefold(), item.key)))


MATCH_STATUSES = {
    "ACQUIS_ETAYE": "Acquis étayé",
    "A_CONFIRMER": "À confirmer en séance",
    "NON_DOCUMENTE": "Non documenté à ce stade",
    "A_DEVELOPPER": "À développer si le bénéficiaire le souhaite",
}

EXERCISE_LEVELS = {
    1: "Pratique encadrée / contribution",
    2: "Maîtrise autonome",
    3: "Pilotage, expertise ou transmission",
}


def validate_review_rows(rows: list[dict[str, Any]], valid_item_keys: set[str], valid_experience_ids: set[str]) -> list[dict[str, Any]]:
    """Validate accompanist decisions before they are persisted."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get("rome_item_key", ""))
        status = str(row.get("status", ""))
        experience_ids = list(dict.fromkeys(str(x) for x in row.get("experience_ids", [])))
        rationale = str(row.get("rationale", "")).strip()
        level_raw = row.get("exercise_level")
        try:
            exercise_level = int(level_raw) if level_raw not in (None, "") else None
        except (TypeError, ValueError):
            raise ValueError("Le niveau d’exercice doit être choisi parmi les niveaux proposés.") from None
        if key not in valid_item_keys or key in seen:
            raise ValueError("Un savoir ROME sélectionné est absent ou dupliqué.")
        if status not in MATCH_STATUSES:
            raise ValueError("Le statut de rapprochement n'est pas reconnu.")
        if any(identity not in valid_experience_ids for identity in experience_ids):
            raise ValueError("Une expérience choisie ne fait pas partie du parcours actif.")
        if status == "ACQUIS_ETAYE" and not experience_ids:
            raise ValueError("Un acquis étayé doit être relié à au moins une expérience.")
        if exercise_level not in (None, *EXERCISE_LEVELS):
            raise ValueError("Le niveau d’exercice doit être compris entre 1 et 3.")
        if status == "ACQUIS_ETAYE" and exercise_level is None:
            raise ValueError("Un acquis étayé doit avoir un niveau d’exercice discuté avec le bénéficiaire.")
        if len(rationale) > 1200:
            raise ValueError("La note de rapprochement dépasse 1 200 caractères.")
        result.append({"rome_item_key": key, "status": status,
                       "experience_ids": experience_ids, "rationale": rationale,
                       "exercise_level": exercise_level})
        seen.add(key)
    if not result:
        raise ValueError("Sélectionnez au moins un savoir ou une compétence ROME.")
    return result
