# CLARTÉ360 — RAPPORT DE TESTS — JALON C

Date : 18/09/2026

## Résultat global

- Tests exécutés : 136
- Tests réussis : 136
- Échecs : 0
- Suite : `pytest -q`

## Contrôles spécifiques Jalon C

Les tests ajoutés vérifient notamment :
- lecture des quatre données d’affichage signées ;
- séparation entre données lisibles et IDs techniques ;
- absence d’affichage des IDs techniques ;
- rétrocompatibilité avec un jeton ancien sans données d’affichage ;
- libellés neutres dans ce cas ;
- interdiction de données dossier en mode PUBLIC ;
- suppression du champ `dialogue` du questionnaire de ressenti ;
- absence de la question interdite « votre accompagnateur » dans les sources utilisateur ;
- traçage du mode dans le ressenti.

## Contrôles de non-régression

- `python scripts/build_pip_runtime.py --check` : OK
- tableur maître V0.6 et runtime PIP-BANK-0.5 synchronisés : OK
- compilation `app.py` + package `clarte360_pip` : OK
- tests historiques A / A1 / B conservés : OK

## Limites

- Pas de recette navigateur interactive réelle dans ce jalon.
- Pas de déploiement VPS.
- Les nouveaux champs d’affichage doivent encore être émis par Gestion des Actions dans son chantier séparé pour que prénom/NOM et intitulé lisible apparaissent réellement en production.
