# Rapport de tests - Intervenants J0

Commande : `PYTHONPATH=. pytest -q`

Resultat : **365 passed in 22.50s**.

- Socle RC2 attendu : 362 tests.
- Nouveaux tests J0 : 3.
- Regression detectee : 0.

Tests J0 : identite stable et liaison 1:1, idempotence de `init_db`, absence d'inference de qualification, preservation de l'etat inactif lors du backfill.
