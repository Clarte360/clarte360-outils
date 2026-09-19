# CLARTÉ360 — PIP RIASEC / O*NET — RAPPORT DE TESTS JALON A1

Date : 18/09/2026

## Résultat automatisé

Commande : `PYTHONPATH=. pytest -q`

- Tests exécutés : 121
- Tests réussis : 121
- Échecs : 0
- Warnings pytest : 0 signalé

## Contrôles spécifiques A1

- 72 items actifs exactement.
- 12 items par dimension R/I/A/S/E/C.
- 30 facettes couvertes, minimum 2 items par facette.
- `item_version = 0.6` sur les 72 items.
- `bank_version = PIP-BANK-0.5`.
- Trois onglets de travail visibles seulement dans le tableur maître.
- Consigne centrée sur l'intérêt professionnel.
- Échelle de réponse 1 à 5 conforme à la formulation « J’aimerais… ».
- Absence d'encadré `exemple_concret` dans le runtime.
- Synchronisation stricte tableur maître / JSON runtime contrôlée par `build_pip_runtime.py --check`.
- Compilation Python des composants modifiés réussie.

## Limites

Les tests A1 sont des tests automatisés de structure, méthode et non-régression. La recette navigateur réelle et la recette VPS restent prévues aux étapes ultérieures conformément au CDC.
