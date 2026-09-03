# RAPPORT DE TESTS — V2 CANDIDATE DE RECETTE RC1

Date : 3 septembre 2026
Version : 2.0.0-rc1

## Résultat automatisé
Commande : `PYTHONPATH=. pytest -q`

**35 tests réussis / 35 — 0 échec.**

La campagne couvre le socle V1, les fonctions V1.1/V1.1.1, la fondation V2, le socle consolidé, le moteur qualité, le pilotage/imports et les contrôles candidate RC1.

## Contrôles RC1 ajoutés
- compilation Python des modules principaux ;
- génération des PDF sous l'identité d'un organisme fictif différent de Clarté360 ;
- version applicative candidate `2.0.0-rc1` ;
- non-régression des 33 tests du jalon I3.

## Limites des tests automatisés
Ces tests ne remplacent pas la recette réelle sur VPS pour : SMTP OVH, Nginx/HTTPS, QR sur smartphone, rendu tactile de signature, affichage multi-écrans, comportement réseau, permissions système et migration sur une copie de la base VPS réelle.
