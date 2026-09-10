"""L1-A source inventory check. L1-B will replace this with the publication pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "sources"
EXPECTED = [
    "CDC_PIP_RIASEC_CLARTE360_ONET_V1_4.docx",
    "REFERENTIEL_METHODOLOGIQUE_PIP_RIASEC_CLARTE360_V1_0.docx",
    "CLARTE360_PIP_RIASEC_TABLEUR_MAITRE_V0_3.xlsx",
    "PIP_RIASEC_CLARTE360_BANQUE_EXPERIMENTALE_120_ITEMS_REVUE_V0_1.docx",
]
missing = [name for name in EXPECTED if not (SRC / name).exists()]
if missing:
    raise SystemExit("Sources manquantes: " + ", ".join(missing))
print("OK - 4 sources PIP cumulatives presentes")
