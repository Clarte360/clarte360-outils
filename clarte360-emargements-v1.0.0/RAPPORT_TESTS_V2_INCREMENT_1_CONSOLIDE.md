# Rapport de tests — V2 incrément intermédiaire n°1 consolidé

Date : 3 septembre 2026

## Résultat

- Compilation Python des modules principaux : OK
- Suite automatisée : **22 tests réussis / 22**
- Commande : `PYTHONPATH=. python -m pytest -q`

## Couverture ajoutée dans cet incrément

- paramétrage organisme et agences ;
- rattachement organisme/agence et modules à une action ;
- verrouillage des modules qualité après campagne envoyée ;
- normalisation des anciens statuts `TERMINEE` / `ARCHIVE` ;
- archivage et désarchivage ;
- recherche par action, client, bénéficiaire et email ;
- réservation atomique des événements email ;
- quarantaine `UNKNOWN_DELIVERY` après interruption ambiguë du worker afin d'éviter un renvoi automatique potentiellement doublonné.

## Important

Ce ZIP est un jalon technique de reprise. Il n'est pas demandé de l'installer ni de le recetter sur le VPS. La recette humaine reste réservée à la candidate V2 complète.
