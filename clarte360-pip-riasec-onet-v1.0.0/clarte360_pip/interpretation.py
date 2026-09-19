from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "resources/runtime/pip_interpretation_PIP-INT-1.0.json"
INTERPRETATION_VERSION = "PIP-INT-1.0"


@lru_cache(maxsize=1)
def load_rules() -> dict:
    if not RULES_PATH.exists():
        raise FileNotFoundError(f"Référentiel runtime d'interprétation absent: {RULES_PATH}")
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    if data.get("interpretation_version") != INTERPRETATION_VERSION:
        raise ValueError("Version du référentiel d'interprétation inattendue.")
    return data


def _clamp(score: float) -> float:
    return max(0.0, min(100.0, float(score)))


def score_band(score: float) -> dict:
    s = _clamp(score)
    rules = load_rules()
    for row in sorted(rules["bands"], key=lambda r: float(r["max_inclus"])):
        if s <= float(row["max_inclus"]):
            return {
                "rule_id": row["rule_id"],
                "label": row["libelle"],
                "text": row["texte_autorise"],
                "min": float(row["min_inclus"]),
                "max": float(row["max_inclus"]),
            }
    raise ValueError(f"Aucune bande d'interprétation ne couvre le score {s}")


def _select_relief(spread: float) -> dict:
    for row in sorted(load_rules()["relief_rules"], key=lambda r: float(r["spread_max_inclus"])):
        if spread <= float(row["spread_max_inclus"]):
            return row
    raise ValueError(f"Aucune règle de relief ne couvre l'amplitude {spread}")


def _select_head_gap(gap: float) -> dict:
    for row in sorted(load_rules()["head_gap_rules"], key=lambda r: float(r["gap_max_inclus"])):
        if gap <= float(row["gap_max_inclus"]):
            return row
    raise ValueError(f"Aucune règle d'écart de tête ne couvre l'écart {gap}")


def profile_shape(indices: dict[str, float], order: list[str]) -> dict:
    if len(order) < 6:
        raise ValueError("Six dimensions ordonnées sont nécessaires.")
    vals = [_clamp(indices[d]) for d in order]
    top, second, third, bottom = vals[0], vals[1], vals[2], vals[-1]
    spread, gap12, gap23 = top - bottom, top - second, second - third

    relief = _select_relief(spread)
    head = _select_head_gap(gap12)
    ctx = {
        "top_code": order[0], "second_code": order[1],
        "top_score": top, "second_score": second,
    }
    return {
        "top": top, "second": second, "third": third, "bottom": bottom,
        "spread": spread, "gap12": gap12, "gap23": gap23,
        "relief_rule_id": relief["rule_id"],
        "relief": relief["libelle"],
        "relief_text": relief["texte_autorise"],
        "head_rule_id": head["rule_id"],
        "top_relation": head["libelle"],
        "top_text": str(head["texte_modele"]).format(**ctx),
    }


def _condition_ok(scenario: dict, values: dict) -> bool:
    tests = (
        ("top_lt", lambda x: values["top"] < x),
        ("top_gte", lambda x: values["top"] >= x),
        ("second_gte", lambda x: values["second"] >= x),
        ("gap12_lte", lambda x: values["gap12"] <= x),
        ("gap12_gte", lambda x: values["gap12"] >= x),
    )
    for key, fn in tests:
        raw = scenario.get(key)
        if raw is not None and not fn(float(raw)):
            return False
    return True


def interpret_pip(indices: dict[str, float], order: list[str]) -> dict:
    rules = load_rules()
    labels = rules["labels"]
    bands = {d: score_band(indices[d]) for d in order}
    shape = profile_shape(indices, order)
    top, second = order[0], order[1]
    ctx = {
        "top_code": top,
        "top_label": labels[top],
        "top_label_lower": labels[top].lower(),
        "top_score": shape["top"],
        "second_code": second,
        "second_label": labels[second],
        "second_score": shape["second"],
        "gap12": shape["gap12"],
        "spread": shape["spread"],
    }
    scenario = next((s for s in rules["summary_scenarios"] if _condition_ok(s, shape)), None)
    if scenario is None:
        raise ValueError("Aucun scénario d'interprétation applicable.")
    return {
        "interpretation_version": INTERPRETATION_VERSION,
        "scenario_rule_id": scenario["rule_id"],
        "bands": bands,
        "shape": shape,
        "headline": str(scenario["headline_modele"]).format(**ctx),
        "summary": str(scenario["summary_modele"]).format(**ctx),
    }
