"""GO22 RC3B : repères SOURCES autorisées, non interprétés, pour C-AV2.

Les rapports ne sont PAS recalculés ici. Un connecteur fournit les résultats
structurés exactement tels qu'affichés dans le document source : score_display
conserve unité et précision d'origine, explanation est sourcée ; aucun résultat
n'est créé à partir d'un titre. Les données de recette sont explicitement FICTIVES.
"""
from __future__ import annotations
import copy

_SOURCE_MAP = {
    "valeurs": "BOUSSOLE_VALEURS", "moteurs": "MOTEURS_PRO",
    "preferences": "PREFERENCES_PRO", "ipip": "IPIP_REPORT", "pip": "PIP_REPORT",
}
_RIASEC = set("RIASEC")
_MAX_ROWS = {"valeurs": 60, "moteurs": 15, "preferences": 10, "ipip": 5, "pip": 6}


def _clean_text(value, label, maximum=350):
    if not isinstance(value, str):
        raise ValueError(f"Repère {label} : texte attendu.")
    result = value.strip()
    if len(result) > maximum:
        raise ValueError(f"Repère {label} : texte trop long.")
    return result


def valid_evidence(evidence, source_refs):
    """Strict, borné et corrélé aux documents déclarés autorisés.

    La présence de ces résumés ne donne pas au Bénéficiaire une nouvelle
    permission de consulter les notes internes ou les documents privés.
    """
    if not isinstance(evidence, dict) or set(evidence) - set(_SOURCE_MAP):
        raise ValueError("Résultats C-AV2 : structure inconnue.")
    allowed = {entry["code"]: entry for entry in source_refs}
    out = {}
    for key, value in evidence.items():
        source_code = _SOURCE_MAP[key]
        if source_code not in allowed or not isinstance(value, dict):
            raise ValueError("Résultats C-AV2 : source non autorisée ou objet invalide.")
        if set(value) != {"scale", "note", "rows", "profile_code", "status"}:
            raise ValueError("Résultats C-AV2 : champs inattendus.")
        if value["status"] != allowed[source_code]["status"]:
            raise ValueError("Statut de simulation non conforme au document source.")
        if key != "pip" and value["profile_code"]:
            raise ValueError("Code RIASEC uniquement dans le rapport PIP.")
        code = _clean_text(value["profile_code"], "Code PIP", 6).upper()
        if code and (len(code) not in (3, 5) or len(set(code)) != len(code) or set(code) - _RIASEC):
            raise ValueError("Code de profil PIP invalide : respecter exactement le rapport (3 ou 5 lettres).")
        rows = value["rows"]
        if not isinstance(rows, list) or len(rows) > _MAX_ROWS[key]:
            raise ValueError("Nombre de repères anormal.")
        cleaned = []
        identifiers = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"key", "label", "explanation", "score_display"}:
                raise ValueError("Repère : structure incomplète.")
            obj = {field: _clean_text(row[field], field, 650 if field == "explanation" else 180)
                   for field in ("key", "label", "explanation", "score_display")}
            if not obj["key"] or not obj["label"] or obj["key"] in identifiers:
                raise ValueError("Repères : intitulés/identifiants invalides ou dupliqués.")
            if key == "pip" and obj["key"] not in _RIASEC:
                raise ValueError("Code de dimension PIP inconnu.")
            identifiers.add(obj["key"])
            cleaned.append(obj)
        if key == "pip" and code and not set(code).issubset(identifiers):
            raise ValueError("Le code RIASEC doit correspondre aux familles présentes dans le rapport.")
        out[key] = {"scale": _clean_text(value["scale"], "Échelle", 300),
                    "note": _clean_text(value["note"], "Précaution de lecture", 650),
                    "rows": cleaned, "profile_code": code, "status": value["status"]}
    return out


def extract_evidence(sources, source_refs):
    """Lit seulement les résumés explicitement saisis par une SOURCE AUTORISÉE.

    Ne fait ni OCR ni analyse IA ; sans résultats disponibles, rien n'est inventé.
    """
    mapping = {entry["code"]: entry for entry in source_refs}
    output = {}
    for key, code in _SOURCE_MAP.items():
        source = sources.get(code)
        if not isinstance(source, dict) or not source.get("authorized") or code not in mapping:
            continue
        if "result_summary" in source:
            output[key] = copy.deepcopy(source["result_summary"])
            output[key]["status"] = source.get("status", "REEL")
    return valid_evidence(output, source_refs)
