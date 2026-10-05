# INCRÉMENT RC2-2-2 RC1 — CORRECTIF DE FINITION AVANT RECETTE — 02/10/2026

Base : `3.0.0-INTERVENANTS-RC2-2-2-P6`.

## Objet
Lever les blocages B1, B2, B3 et renforcer B5 identifiés par l'audit `AUDIT_RC2_2_2_AVANT_RECETTE_20261002.md`, sans modifier l'architecture métier P1-P6.

## Corrections
- Version applicative : `3.0.0-INTERVENANTS-RC2-2-2-RC1`.
- Assertions historiques de version réalignées sur RC1.
- Nouveau module `workflow_navigation.py` : état de navigation Action -> bonne personne/prestation -> retour Action testable hors Streamlit.
- `app.py` utilise ces fonctions pour l'aller-retour métier C5.
- Deux tests RC1 ajoutés pour C5 : cas devenu QUALIFIÉ et cas restant NIVEAU_INSUFFISANT.
- Nettoyage de package : suppression de `backups/`, données de documents/signatures de test, caches pytest, `__pycache__`, `.pyc`, logs/tmp runtime.

## Non traité dans ce jalon
- Le scénario C5 reste à rejouer visuellement en recette humaine finale.
- La campagne monolithique `PYTHONPATH=. pytest -q` reste à exécuter dans un environnement sans limite de durée avant validation définitive RECETTE/VPS.
- Aucun PUSH GitHub et aucun déploiement VPS.
