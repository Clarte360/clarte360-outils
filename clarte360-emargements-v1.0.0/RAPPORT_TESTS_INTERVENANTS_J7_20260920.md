# Rapport de tests — Intervenants J7

Date : 20/09/2026

Résultat : **403/403 tests réussis — 0 régression**.

Le socle J6 comptait 398 tests. J7 ajoute 5 tests :
1. détection document échu / à renouveler ;
2. détection Qualiopi et habilitation/certification à échéance ;
3. révision de qualification signalée sans invalidation automatique du niveau humain ;
4. report, réouverture et traitement d'une alerte ;
5. archivage logique d'un document sans destruction du fichier stocké.

Commande : `PYTHONPATH=. pytest -q`
Résultat : `403 passed`.
