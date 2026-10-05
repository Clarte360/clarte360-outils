# RAPPORT DE TESTS — INTERVENANTS RC2-2-2 P1 — 02/10/2026

## Version testée
`3.0.0-INTERVENANTS-RC2-2-2-P1`

Base de départ : RC2-2-1 officielle OneDrive, baseline VPS connue : 475/475 tests verts.

## Contrôles P1 dédiés
Commande :
`PYTHONPATH=. pytest -q tests/test_intervenants_rc2_2_2_p1_data.py`

Résultat : **9 passed**.

Couverture :
1. nouvelle liste de collaboration et migration contrôlée des anciennes valeurs ;
2. idempotence de migration ;
3. absence de verrou humain sur une proposition IA seule ;
4. protection automatique d'une décision humaine globale et par critère ;
5. réparation des anciens verrous incohérents lors de `init_db()` ;
6. transformation idempotente des anciens `ai_missing_json` en points structurés, décision et réouverture ;
7. provenance d'un fait IA accepté et réutilisation dans plusieurs prestations sans duplication ;
8. provenance humaine/migration persistante et suppression contrôlée des objets P1 ;
9. modification humaine d'un fait structurée et nettoyage de ses liens génériques lors de la suppression.

## Non-régression Intervenants
Les 22 fichiers `test_intervenants_*.py` ont été exécutés en deux lots disjoints après le dernier correctif P1 :
- lot Intervenants A : **46 passed** ;
- lot Intervenants B : **59 passed**.

Total Intervenants : **105 passed**.

## Non-régression du reste de l'application
La commande monolithique complète dépasse la fenêtre maximale d'exécution disponible dans l'environnement de construction. Pour ne pas confondre timeout d'environnement et échec de test, tous les fichiers restants ont été exécutés par quatre lots disjoints, triés, couvrant 100 % des tests non `test_intervenants_*` :

- lot 1 : **139 passed** ;
- lot 2 : **102 passed** ;
- lot 3 : **118 passed** ;
- lot 4 : **20 passed**.

Total non-Intervenants : **379 passed**.

Total exhaustif P1 exécuté : **484 passed, 0 échec** (105 Intervenants + 379 autres).

Le passage de 475 à 484 correspond aux 9 nouveaux tests P1 ; aucun test historique n'a été supprimé.

## Compilation
Commande :
`PYTHONPATH=. python -m compileall -q .`

Résultat : **OK**.

## Limite à conserver pour la future RC/VPS
Le CDC exige avant ZIP de recette finale la campagne exacte :
`PYTHONPATH=. ./.venv/bin/pytest -q`

Cette campagne devra être exécutée en une seule commande sur l'environnement de recette/VPS avant validation de RC2-2-2. Le présent jalon P1 n'est pas la recette finale et ne remplace pas cette obligation.

## Nettoyage package
Après tests, les artefacts runtime générés par pytest ont été supprimés/restaurés depuis la base officielle : caches Python/pytest, signatures de test, documents professionnels de test et snapshots de reset. Aucun fichier `.db`, `.sqlite`, `.sqlite3` ou `.pyc` n'est destiné au package P1.

## Conclusion
**P1 Données : tests techniques verts sur la totalité des 484 tests exécutés, 0 échec.**

Aucun déploiement VPS ni PUSH GitHub n'est réalisé à ce jalon.
