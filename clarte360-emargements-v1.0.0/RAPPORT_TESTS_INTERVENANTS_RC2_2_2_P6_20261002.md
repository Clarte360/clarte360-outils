# Tests RC2-2-2 — P6 — 02/10/2026

- Tests ciblés CV historiques + P6 : 10/10 verts.
- 5 nouveaux tests P6 : régénération sur changement source, confidentialité audience, exclusion IA non validée, anti-doublon, migration additive.
- Suite exhaustive : 90 fichiers de tests, 511 tests au total, exécutés par lots à cause de la limite d'exécution de l'environnement ; 511/511 verts, 0 échec.
- Compilation : `PYTHONPATH=. python -m compileall -q .` verte.
- Le lancement monolithique `pytest -q` dépasse la fenêtre d'exécution de l'environnement ; la campagne exhaustive par lots couvre tous les mêmes fichiers. La campagne monolithique réglementaire reste à refaire au jalon RC/VPS avant validation du ZIP RECETTE.
