# Rapport de tests — I9-H2.3

Date : 15/09/2026

## Périmètre

Consolidation de la dernière H2.2 HUB REGISTRY avec les constats de recette réelle : preuves Microsoft Teams, ergonomie administrateur/intervenant/bénéficiaire, verrouillage des chevauchements de créneaux, preuve de signature manuscrite substantielle, certificat bénéficiaire uniquement après clôture.

## Résultats

- Pytest : 278 réussis / 278
- Compilation Python : OK
- Imports principaux : OK
- release_check.py : CANDIDATE TECHNIQUE OK

## Tests H2.3 ajoutés

- refus d'un créneau qui chevauche un autre créneau de la même action ;
- acceptation de créneaux adjacents ;
- rapprochement d'un attendance report uniquement dans la fenêtre créneau ±30 minutes ;
- persistance JSON Graph + empreinte SHA-256 ;
- maintien d'une connexion Teams non rapprochée sans attribution silencieuse ;
- rejet d'un canvas vide ou d'un tap / point ;
- acceptation d'un tracé manuscrit substantiel ;
- conservation de la configuration d'évaluation à froid après clôture.
