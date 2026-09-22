# RAPPORT DE TESTS — INTERVENANTS J17
Date : 21/09/2026

## Tests ciblés Intervenants
Commande : `PYTHONPATH=. pytest -q tests/test_intervenants_*.py`
Résultat : **78 tests réussis / 78 — 0 échec**.

Les nouveaux tests J17 vérifient notamment :
- maintien visible du statut NON_QUALIFIE après une affectation exceptionnelle ;
- recalcul en QUALIFIE après validation humaine ;
- distinction NIVEAU_INSUFFISANT avec niveaux constaté/requis ;
- état A_VERIFIER lorsqu'aucune prestation n'est rattachée ;
- pont trainer_id / professional_person_id ;
- suggestions catalogue sans sélection automatique.

## Compilation
`python -m py_compile app.py services.py` : OK.

## Non-régression globale
Une exécution globale `pytest -q` a été lancée. Elle a atteint environ **65 %** de la suite sans échec affiché avant la limite de temps d'exécution de 45 secondes. Elle n'est donc pas déclarée complète. La non-régression exhaustive est réservée au J18 final, conformément au plan validé.

## Conclusion
J17 satisfait le périmètre Action → Prestation → Intervenant prévu par le CDC correctif. GO technique pour passage au J18 de recette finale corrigée.
