# Rapport de tests - Jalon H - 18/09/2026

## Pytest
Résultat : **174 passed, 0 failed**.

## Contrôles de synchronisation
- Sources cumulatives PIP : OK.
- Banque PIP / runtime JSON : OK.
- Référentiel d'interprétation / runtime JSON : OK.
- ROME / runtime JSON : OK - 1 911 fiches, `ROME-RIASEC-2026-06`.

## Compilation
`python -m compileall -q app.py clarte360_pip scripts tests` : OK.

## Recette finale spécifique H
- version de jalon/build H : testée ;
- prudence PUBLIC dans le PDF : testée ;
- mention obligatoire ACCOMPAGNEMENT dans le PDF : testée ;
- synchronisation des trois référentiels runtime : testée ;
- non-régressions A à G : incluses dans la suite complète.

## PDF
- PIP PUBLIC : génération OK ; rendu 9 pages contrôlé.
- PIP ACCOMPAGNEMENT : génération OK ; rendu 9 pages contrôlé.
- O*NET : génération OK ; rendu 6 pages contrôlé.

## Limite volontaire
Aucune recette VPS n'est déclarée réussie ici, car aucun déploiement n'a encore été effectué. Elle sera exécutée après le push GitHub Desktop confirmé par l'utilisateur.
