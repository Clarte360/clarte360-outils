# RAPPORT DE TESTS — INTERVENANTS RC2-2-2 P2 — 02/10/2026

## Tests P2 ciblés
Fichier : `tests/test_intervenants_rc2_2_2_p2_ai.py`

Résultat : **6 passed / 6**.

Couverture :
- faux 0/4 corrigé lorsqu'un élément positif existe ;
- maintien de 0/4 en absence réelle de tout élément positif ;
- séparation des critères obligatoires insuffisants ;
- appels API / retries / tokens / durée / coût estimatif ;
- détection PDF hybride sans OCR ;
- persistance des métriques ;
- création directe des points IA structurés ;
- présence des raccordements UI P2.

## Régression IA / Intervenants ciblée
Tests J5/J14/J16/RC2-1/RC2-2/P1/P2 : **40 passed / 40**.

## Suite complète
`pytest --collect-only` : **490 tests collectés**.

La durée totale de la suite excède la limite d'un appel unique de l'environnement de construction. La suite a donc été exécutée par lots couvrant exhaustivement les 86 fichiers `tests/test_*.py` :
- lot 0-14 : 129 passed ;
- lot 15-19 : 20 passed ;
- lot 20-24 : 22 passed ;
- lot 25-34 : 52 passed ;
- lot 35-44 : 41 passed ;
- lot 45-54 : 50 passed ;
- lot 55-64 : 47 passed ;
- lot 65-74 : 59 passed ;
- lot 75-85 : 70 passed.

**Total : 490/490 tests verts, 0 échec.**

## Compilation
`PYTHONPATH=. python -m compileall -q .` : **OK**.

## Package
Le package final P2 exclut les bases runtime, documents professionnels, signatures, caches Python, `.pytest_cache`, sauvegardes de runtime et secrets réels.

## Statut
P2 validé techniquement en environnement de construction. Aucun déploiement VPS n'a été réalisé à ce jalon.
