# Correctif urgent RC1.1 - 4 septembre 2026

Objectif : securiser les demandes d'emargement avant la prochaine action.

## Corrections
1. Envoi manuel : suppression du `NameError: PRIVACY_NOTICE is not defined`.
2. Worker automatique : ne depend plus d'un prefiltrage SQL sur une `due_at` potentiellement corrompue. Chaque evenement PENDING d'une action ACTIVE/A_CLOTURER est recalcule a partir du creneau et du fuseau de l'organisme avant envoi.
3. Protection anti-envoi premature conservee.

## Validation
`python3 -m pytest -q` : **76 passed**.

## Non inclus dans ce correctif urgent
La contresignature graphique de l'intervenant est a traiter dans le lot suivant ; la RC1.1 ne modifie pas le schema ni la preuve existante afin de limiter le risque avant l'action suivante.
