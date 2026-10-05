# RAPPORT TESTS — RC2-2-2 RC1 — 02/10/2026

## Tests ciblés correctif
- Navigation C5 RC1 + P5 + contrôles version historiques : **26/26 verts**.

## Campagne exhaustive par lots
91 fichiers de tests, **513 tests exécutés, 513 verts, 0 échec** :
- lot AA : 146 verts ;
- lot AB : 81 verts ;
- lot AC : 73 verts ;
- lot AD scindé : 53 + 49 = 102 verts ;
- lot AE : 111 verts.

Le lot AD initial avait dépassé la fenêtre d'exécution après 70 % sans échec ; il a donc été rejoué intégralement en deux sous-lots, tous deux verts.

## Compilation
`python -m compileall -q branding.py app.py workflow_navigation.py tests/test_intervenants_rc2_2_2_rc1_navigation.py` : OK avant nettoyage des caches générés.

## Limite connue
La campagne monolithique `PYTHONPATH=. pytest -q` n'est pas déclarée validée dans cet environnement ; elle reste obligatoire avant validation définitive du ZIP RECETTE/VPS.
