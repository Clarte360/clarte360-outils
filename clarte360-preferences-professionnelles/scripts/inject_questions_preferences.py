"""Injection du questionnaire Clarte360 Preferences professionnelles.

Usage:
    python scripts/inject_questions_preferences.py data/questions_preferences_professionnelles_v1.xlsx data/questions_preferences_professionnelles_v1.json

Objectif:
- lire le fichier Excel officiel ;
- controler la structure et les cotations ;
- generer un JSON stable pour l'application ou pour archivage ;
- tracer la version et les erreurs eventuelles.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
    "ID", "Dimension", "Libelle dimension", "Question",
    "Reponse A", "Score A", "Reponse B", "Score B", "Reponse C", "Score C", "Reponse D", "Score D",
    "Max question", "Statut", "Version"
]
EXPECTED_DIMS = [f"PP{i}" for i in range(1, 11)]


def load_questions(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Questions")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def validate(df: pd.DataFrame) -> list[str]:
    errors = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return ["Colonnes manquantes : " + ", ".join(missing)]

    if df["ID"].astype(str).str.strip().duplicated().any():
        errors.append("ID question en doublon.")

    for col in ["Question", "Reponse A", "Reponse B", "Reponse C", "Reponse D", "Dimension", "Statut"]:
        if df[col].isna().any() or df[col].astype(str).str.strip().eq("").any():
            errors.append(f"Cellule vide detectee dans {col}.")

    for col in ["Score A", "Score B", "Score C", "Score D", "Max question"]:
        vals = pd.to_numeric(df[col], errors="coerce")
        if vals.isna().any():
            errors.append(f"Valeur non numerique dans {col}.")
        if col.startswith("Score") and ((vals < 0) | (vals > 3)).any():
            errors.append(f"Score hors plage 0-3 dans {col}.")

    active = df[df["Statut"].astype(str).str.lower().str.strip() == "active"].copy()
    if len(active) != 60:
        errors.append(f"Nombre de questions actives attendu : 60. Trouve : {len(active)}.")

    counts = active.groupby(active["Dimension"].astype(str).str.strip()).size().to_dict()
    for dim in EXPECTED_DIMS:
        if counts.get(dim, 0) != 6:
            errors.append(f"{dim} doit avoir 6 questions actives. Trouve : {counts.get(dim, 0)}.")
    return errors


def build_payload(df: pd.DataFrame, source: Path) -> dict:
    questions = []
    for _, row in df.iterrows():
        options = []
        for opt in ["A", "B", "C", "D"]:
            options.append({
                "option": opt,
                "text": str(row[f"Reponse {opt}"]).strip(),
                "score": float(row[f"Score {opt}"]),
            })
        questions.append({
            "id": str(row["ID"]).strip(),
            "dimension": str(row["Dimension"]).strip(),
            "dimension_label": str(row["Libelle dimension"]).strip(),
            "question": str(row["Question"]).strip(),
            "options": options,
            "max_question": float(row["Max question"]),
            "status": str(row["Statut"]).strip(),
            "version": str(row["Version"]).strip(),
        })
    return {
        "tool": "clarte360_preferences_professionnelles",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": str(source.name),
        "rules": {
            "active_questions_expected": 60,
            "dimensions": EXPECTED_DIMS,
            "questions_per_dimension": 6,
            "score_min": 0,
            "score_max": 3,
            "display_order": "randomized_at_each_session",
            "dimension_labels_visible_to_user": False,
        },
        "questions": questions,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/inject_questions_preferences.py <input.xlsx> <output.json>")
        return 2
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    df = load_questions(input_path)
    errors = validate(df)
    if errors:
        print("ERREURS D'INJECTION")
        for err in errors:
            print("-", err)
        return 1
    payload = build_payload(df, input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Injection OK : {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
