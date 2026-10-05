# RAPPORT TESTS RC2-2-2 RC2
Date : 02/10/2026

- Collecte : 521 tests / 92 fichiers.
- Lot A : 162 passed.
- Lot B : 109 passed.
- Lot C : 112 passed.
- Lot D : 138 passed.
- Total : 521/521 verts, 0 echec.
- Tests specifiques conformite CDC RC2 : 8/8 verts.
- Compilation : `PYTHONPATH=. python -m compileall -q .` OK avant nettoyage des caches.
- Package nettoye : aucun `__pycache__`, `.pyc`, `.pytest_cache`, base runtime ou fichier SQLite inclus.

La campagne monolithique reste a rejouer sur VPS/environnement de recette conformement au CDC, car la limite d'execution locale impose les lots.
