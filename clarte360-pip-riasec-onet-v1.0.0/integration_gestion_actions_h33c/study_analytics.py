from __future__ import annotations

from collections import Counter
from typing import Any

RIASEC = ("R", "I", "A", "S", "E", "C")
ONET_CODE_MAP = {
    "realistic": "R",
    "investigative": "I",
    "artistic": "A",
    "social": "S",
    "enterprising": "E",
    "conventional": "C",
    "r": "R", "i": "I", "a": "A", "s": "S", "e": "E", "c": "C",
}
REQUIRED_FEELING_KEYS = ("global", "dominants", "nuances", "useful")


def _pct(n: int, total: int) -> float:
    return round((100.0 * n / total), 1) if total else 0.0


def _valid_order(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    order = [str(v).upper().strip() for v in values]
    return order if len(order) == 6 and set(order) == set(RIASEC) else []


def pip_order(record: dict) -> list[str]:
    return _valid_order((record.get("pip_scoring") or {}).get("order"))


def onet_order(record: dict) -> list[str]:
    onet = record.get("onet_state") or {}
    if onet.get("completed") is not True:
        return []
    rows = onet.get("results") or []
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = ONET_CODE_MAP.get(str(row.get("code", "")).strip().lower())
        if not code:
            continue
        try:
            score = float(row.get("score"))
        except (TypeError, ValueError):
            continue
        normalized.append((code, score))
    if len(normalized) != 6 or len({x[0] for x in normalized}) != 6:
        return []
    normalized.sort(key=lambda x: (-x[1], RIASEC.index(x[0])))
    return [x[0] for x in normalized]


def feeling_is_exploitable(record: dict) -> bool:
    answers = ((record.get("feeling") or {}).get("answers") or {})
    return all(answers.get(k) in (1, 2, 3, 4, 5) for k in REQUIRED_FEELING_KEYS)


def record_is_termine(record: dict) -> bool:
    # H3.3+ explicit status is authoritative when present.
    status = str(record.get("status") or "").upper().strip()
    if status:
        return status == "TERMINE"
    # Legacy H3.2 compatibility: completed_at alone is not sufficient because
    # older records could be written before the mandatory feeling step.
    return bool(record.get("completed_at") and feeling_is_exploitable(record))


def population_summary(records: list[dict]) -> dict:
    pip_records = [r for r in records if pip_order(r)]
    pairs = [r for r in pip_records if onet_order(r)]
    pip_only = [r for r in pip_records if not onet_order(r)]
    feeling = [r for r in pip_records if feeling_is_exploitable(r)]
    return {
        "n_records": len(records),
        "n_pip": len(pip_records),
        "n_pip_onet": len(pairs),
        "n_pip_only": len(pip_only),
        "n_feeling": len(feeling),
        "n_termine": sum(record_is_termine(r) for r in records),
    }


def individual_concordance(record: dict) -> dict | None:
    p = pip_order(record)
    o = onet_order(record)
    if not p or not o:
        return None
    matches = [p[i] == o[i] for i in range(6)]
    return {
        "study_id": record.get("study_id"),
        "timing": record.get("onet_selected_timing"),
        "matches": matches,
        "same_positions": sum(matches),
    }


def concordance_summary(records: list[dict]) -> dict:
    rows = [x for x in (individual_concordance(r) for r in records) if x is not None]
    n = len(rows)
    hist = Counter(x["same_positions"] for x in rows)
    distribution = [
        {"positions_identiques": k, "n": hist.get(k, 0), "N": n, "pourcentage": _pct(hist.get(k, 0), n)}
        for k in range(6, -1, -1)
    ]
    positions = []
    for idx in range(6):
        count = sum(1 for x in rows if x["matches"][idx])
        positions.append({"position": idx + 1, "n": count, "N": n, "pourcentage": _pct(count, n)})
    mean = round(sum(x["same_positions"] for x in rows) / n, 2) if n else 0.0
    return {"N": n, "mean_same_positions": mean, "distribution": distribution, "positions": positions}


def feeling_summary(records: list[dict]) -> dict:
    question_meta: dict[str, dict] = {}
    answers_by_key: dict[str, list] = {}
    for r in records:
        feeling = r.get("feeling") or {}
        questions = feeling.get("questions") or {}
        answers = feeling.get("answers") or {}
        for key, val in answers.items():
            if key not in questions:
                continue
            q = questions.get(key) or {}
            question_meta.setdefault(key, {"text": q.get("text") or key, "kind": q.get("kind")})
            answers_by_key.setdefault(key, []).append(val)

    scale_rows = []
    delta_rows = []
    for key, vals in answers_by_key.items():
        meta = question_meta.get(key, {"text": key, "kind": None})
        if meta.get("kind") == "scale5" or key in REQUIRED_FEELING_KEYS:
            clean = [int(v) for v in vals if v in (1, 2, 3, 4, 5)]
            n = len(clean)
            row = {"key": key, "question": meta["text"], "n": n}
            for score in range(1, 6):
                c = clean.count(score)
                row[f"n_{score}"] = c
                row[f"pct_{score}"] = _pct(c, n)
            scale_rows.append(row)
        elif meta.get("kind") == "delta" or key in ("over", "under"):
            clean = [str(v) for v in vals if str(v) in ("Aucune",) + RIASEC]
            n = len(clean)
            counts = Counter(clean)
            delta_rows.append({
                "key": key,
                "question": meta["text"],
                "n": n,
                "modalites": [
                    {"modalite": m, "n": counts.get(m, 0), "N": n, "pourcentage": _pct(counts.get(m, 0), n)}
                    for m in ("Aucune",) + RIASEC
                ],
            })
    return {"scale": scale_rows, "delta": delta_rows}
