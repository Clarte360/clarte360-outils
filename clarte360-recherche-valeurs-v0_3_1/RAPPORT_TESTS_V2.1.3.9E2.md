# Rapport de tests V2.1.3.9E2-preproduction

## Résultat

- Compilation Python : réussie.
- Suite Pytest : **86 tests réussis sur 86**.
- Aucun échec.

## Contrôles ajoutés pour la 9E2

1. Le nom d'une valeur conserve toujours l'option permettant de garder la formulation écrite initiale.
2. La transcription orale initiale reste toujours sélectionnable pour un nom de valeur.
3. Ctrl + Entrée est installé sur tous les champs écrits.
4. Le raccourci déclenche le bouton principal correspondant au parcours : validation directe ou préparation/comparaison.

## Limite connue

Le JavaScript du raccourci est contrôlé structurellement dans la suite automatisée. Son comportement final doit être confirmé une fois sous Chrome ou Edge dans l'environnement Streamlit cible.
