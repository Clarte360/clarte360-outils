# Rapport de tests — V3.0.0-I9-E

Date : 12/09/2026

Commande :

`PYTHONPATH=. pytest -q`

Résultat : **165 passed in 15.55s**

Compilation :

`python -m compileall -q .`

Résultat : **COMPILE_OK**

## Couverture spécifique I9-E

- table additive de curseur connecteur ;
- compatibilité cryptographique HMAC-SHA256 avec le contrat RC5 ;
- URL exacte `mode=accompagnement&launch=...` ;
- absence de PII dans le jeton ;
- lancement depuis une prescription réelle du Hub ;
- consommation des événements CONSULTÉ / EN_COURS / TERMINÉ ;
- idempotence après nouvelle lecture ;
- rejet d'un croisement d'identité ;
- non-consommation d'une ligne JSONL partielle ;
- traitement PIP avant le garde SMTP du worker ;
- statut runtime sans stockage de secret ;
- UI bénéficiaire sans information technique en cas d'erreur.

Aucun test réel contre le VPS ou le secret de production n'a été exécuté à ce stade, conformément au plan de recette finale.
