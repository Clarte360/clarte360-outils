# RAPPORT DE TESTS — INTERVENANTS RC2-2 — 01/10/2026

Version : **3.0.0-INTERVENANTS-RC2-2**

## Compilation

Commande :

`python3 -m compileall -q .`

Résultat : **OK**.

## Tests automatisés

La suite contient **465 tests** après ajout des contrôles RC2-2.

Dans l’environnement de construction, une exécution monolithique de `python3 -m pytest -q` dépasse la fenêtre maximale d’exécution du conteneur avant la fin, sans afficher d’échec avant interruption. Pour obtenir une validation exhaustive sans contourner de tests, les **82 fichiers de tests** ont été exécutés dans quatre partitions couvrant l’intégralité de la suite :

- lot 1 : **152 passed** ;
- lot 2 : **94 passed** ;
- lot 3 : **101 passed** ;
- lot 4 : **118 passed**.

Total : **465 / 465 tests réussis — 0 échec**.

## Tests RC2-2 ajoutés

- séparation identité / titre professionnel ;
- mise à jour prénom/nom ;
- même nom + empreinte SHA-256 différente = nouvelle version ;
- même nom + même empreinte = doublon exact non recréé ;
- purge protégée par mot de passe administrateur ;
- conservation identité/statut/activité/documents après purge ;
- idempotence des faits structurés acceptés ;
- suppression physique d’un dossier contenant uniquement des données internes ;
- blocage de suppression en présence d’une utilisation dans une action ;
- transmission d’un PDF scanné comme `input_file` à la passerelle IA ;
- contrôle statique du menu Intervenants / Partenaires ;
- priorité d’affichage de la décision humaine ;
- suppression du bouton Retenir pour instruction ;
- distinction « Aucun élément repéré » / « Éléments repérés — niveau global bloqué ».

## Contrôle obligatoire avant déploiement VPS

Après intégration du ZIP dans GitHub puis mise à jour de la copie VPS, exécuter impérativement dans l’environnement virtuel réel :

`PYTHONPATH=. ./.venv/bin/pytest -q`

puis :

`PYTHONPATH=. ./.venv/bin/python -m compileall -q .`

Le déploiement ne sera considéré validable qu’après cette campagne monolithique verte sur le VPS et la recette métier RC2-2.
