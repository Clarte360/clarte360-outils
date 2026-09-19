# CLARTÉ360 — PIP RIASEC / O*NET — Jalon E3
Date : 18/09/2026
Base : Jalon E2 officiel OneDrive

## Objet
Corriger la gouvernance méthodologique du moteur d'interprétation PIP : les règles ne doivent pas être définies seulement dans le code.

## Référentiel créé
`docs/sources/REFERENTIEL_INTERPRETATION_PIP_RIASEC_CLARTE360_V1_0.xlsx`

Version méthodologique : `PIP-INT-1.0`.

Le classeur documente :
- les 6 dimensions RIASEC et leurs descriptions ;
- les 5 bandes descriptives de niveau PIP ;
- les règles de relief global ;
- les règles d'écart entre les deux premières dimensions ;
- les scénarios de synthèse et leurs textes autorisés ;
- les garde-fous méthodologiques ;
- les cas de recette lisibles humainement ;
- le changelog du référentiel.

## Architecture
Source métier : tableur d'interprétation
→ génération contrôlée
→ `resources/runtime/pip_interpretation_PIP-INT-1.0.json`
→ moteur `clarte360_pip/interpretation.py`
→ rapport PIP.

Le moteur ne contient plus les seuils et textes métier en dur. Il applique le runtime généré depuis le référentiel.

## Gouvernance
Une future modification d'un seuil ou d'un texte se fait dans le tableur, puis :
1. régénération du runtime ;
2. contrôle `--check` ;
3. exécution des tests ;
4. commit du tableur + JSON généré + changelog.

## Versions
- Interprétation : `PIP-INT-1.0`
- Rapport PIP : `PIP-RPT-1.3`
- Rapport O*NET : `ONET-RPT-1.1` (inchangé)
- Banque PIP : `PIP-BANK-0.5` (inchangée)
- Tableur maître des questions : V0.6 (inchangé)
- Scoring PIP : inchangé
