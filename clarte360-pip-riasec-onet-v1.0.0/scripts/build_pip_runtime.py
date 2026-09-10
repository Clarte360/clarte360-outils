from __future__ import annotations
import json
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs/sources/CLARTE360_PIP_RIASEC_TABLEUR_MAITRE_V0_3.xlsx"
OUT = ROOT / "resources/runtime/pip_bank_PIP-BANK-0.3.json"

wb = openpyxl.load_workbook(SRC, data_only=True)
# Le pipeline complet L1-B reste la source de verite de transformation.
# Ce script conserve volontairement la destination versionnee hors data/ afin
# d'etre compatible avec le .gitignore racine du monorepo VPS.
if not OUT.parent.exists():
    OUT.parent.mkdir(parents=True)

# Le contenu runtime est deja versionne et valide. Ne pas reconstruire sans
# appliquer les controles metier L1-B. Cette garde evite une ecriture sauvage.
current = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
if current is None:
    raise RuntimeError("Ressource runtime absente: utiliser le pipeline valide L1-B.")
OUT.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Runtime valide conserve: {OUT.relative_to(ROOT)}")
