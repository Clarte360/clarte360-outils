# RAPPORT DE TESTS — INTERVENANTS RC2-2-2 P3 — 02/10/2026

## Tests ciblés P1/P2/P3
`tests/test_intervenants_rc2_2_2_p1_data.py`, `tests/test_intervenants_rc2_2_2_p2_ai.py`, `tests/test_intervenants_rc2_2_2_p3_ux.py` : **24/24 verts**.

## Suite exhaustive
`pytest --collect-only` après ajout du dernier contrôle P3 : **499 tests**.
La campagne monolithique dépasse la fenêtre d'exécution de l'environnement ; elle a donc été exécutée par lots disjoints couvrant les 87 fichiers `tests/test_*.py` :
- fichiers 0-14 : 129 passed ;
- 15-19 : 20 passed ;
- 20-24 : 22 passed ;
- 25-34 : 58 passed ;
- 35-44 : 38 passed ;
- 45-54 : 51 passed ;
- 55-64 : 49 passed ;
- 65-74 : 58 passed ;
- 75-86 : 74 passed.

**Total : 499/499 verts, 0 échec.**

## Compilation
`PYTHONPATH=. python -m compileall -q .` : **OK**.

## Remarque RC
Conformément au CDC, la campagne exacte `PYTHONPATH=. ./.venv/bin/pytest -q` reste obligatoire sur l'environnement de recette/VPS avant constitution de la RC finale.
