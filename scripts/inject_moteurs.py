"""Validation et export JSON du questionnaire Clarté360 – Moteurs professionnels."""
import json
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
XLSX = BASE / "data" / "moteurs_professionnels_curseurs_v0_1.xlsx"
OUT = BASE / "data" / "moteurs_professionnels_curseurs_v0_1.json"

REQUIRED = ["ID", "Situation / consigne", "Proposition gauche", "Proposition droite", "Moteur gauche", "Moteur droite", "Position défaut", "Statut", "Version"]


def main():
    curseurs = pd.read_excel(XLSX, sheet_name="Curseurs")
    curseurs.columns = [str(c).strip() for c in curseurs.columns]
    missing = [c for c in REQUIRED if c not in curseurs.columns]
    if missing:
        raise SystemExit("Colonnes manquantes : " + ", ".join(missing))
    active = curseurs[curseurs["Statut"].astype(str).str.lower().str.strip() == "active"].copy()
    if len(active) != 60:
        raise SystemExit(f"Il faut 60 curseurs actifs. Actuellement : {len(active)}")
    if active["ID"].astype(str).duplicated().any():
        raise SystemExit("ID en doublon")
    dims = pd.read_excel(XLSX, sheet_name="Dimensions")
    params = pd.read_excel(XLSX, sheet_name="PARAMETRES")
    payload = {
        "source": XLSX.name,
        "curseurs": active.fillna("").to_dict(orient="records"),
        "dimensions": dims.fillna("").to_dict(orient="records"),
        "parametres": params.fillna("").to_dict(orient="records"),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK : {OUT}")

if __name__ == "__main__":
    main()
