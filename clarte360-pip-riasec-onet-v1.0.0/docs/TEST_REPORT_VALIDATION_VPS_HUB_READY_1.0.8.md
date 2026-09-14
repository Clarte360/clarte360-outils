# Rapport de tests — PIP 1.0.8 VALIDATION-SAISIES-VPS-HUB-READY

## Avant modification

Suite source RC5 : **61 tests réussis**.

## Après modification

Suite complète : **103 tests réussis**.

Couverture ajoutée : noms internationaux, noms invalides, e-mails et injections d’en-têtes, téléphones internationaux et aberrants, scores/bornes/NaN/infini, codes à 6 chiffres, identifiants/traversal, URL HTTPS, prévention formule tableur, JSON vide/malformé/surdimensionné, reprise invalide, contrat Hub I9-H1, scopes, tool_id et identité applicative.

Compilation Python : **OK** sur `app.py`, `clarte360_pip/` et `tests/`. Imports du noyau non-UI : **OK (7 modules)**. Le conteneur d’audit ne contient pas le paquet `streamlit`, donc l’import dynamique des modules UI n’a pas été utilisé comme critère ; leur syntaxe est couverte par `compileall` et leur comportement par la suite pytest existante. La recette VPS devra naturellement exécuter les imports avec le `.venv` réel de l’application.
