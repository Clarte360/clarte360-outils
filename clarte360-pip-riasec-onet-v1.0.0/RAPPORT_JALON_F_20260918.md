# CLARTÉ360 PIP RIASEC / O*NET — Jalon F

Date : 18/09/2026
Base : Jalon E3 officiel récupéré depuis OneDrive.

## Objet
Intégration du référentiel ROME/RIASEC au rapport PIP Clarté360, conformément au CDC. Aucune modification de Gestion des Actions.

## Référentiel
- Source : `docs/references/rome_riasec_clarte360.xlsx`
- Contrôle source : 1 911 fiches ROME au statut OK.
- Date ROME portée par le référentiel : juin 2026.
- Version runtime : `ROME-RIASEC-2026-06`.
- Le tableur source reste la source métier ; `scripts/build_rome_runtime.py` génère un JSON runtime contrôlable par `--check`.

## Logique d’exploration
- Le moteur utilise prioritairement les deux premières lettres du profil RIASEC PIP.
- Le profil à deux lettres n’est pas forcé en cas d’égalité exacte au premier rang ou à la frontière rang 2 / rang 3.
- Recherche sur correspondance exacte `RIASEC normalise` du référentiel.
- Au maximum 6 fiches sont affichées.
- La sélection est déterministe et diversifiée autant que possible par grande famille de code ROME afin d’éviter une liste de métiers quasi identiques.
- Aucun score de compatibilité, classement métier, recommandation ou prescription n’est calculé.

## Rapport PIP
Version : `PIP-RPT-1.4`.

Nouvelle section : **Pistes de métiers à explorer**.
Elle explique explicitement que les fiches sont des supports d’exploration et qu’un choix professionnel doit être confronté aux compétences, qualifications, valeurs, moteurs, préférences, contraintes, équilibre de vie, conditions de travail et réalité du marché.

Le rapport O*NET reste indépendant et inchangé (`ONET-RPT-1.1`).

## Non-régression
- Banque PIP : `PIP-BANK-0.5`, inchangée.
- Interprétation PIP : `PIP-INT-1.0`, inchangée.
- Scoring : `PIP-SCORE-0.5`, inchangé.
- O*NET : aucune fusion avec les pistes ROME du rapport PIP.
