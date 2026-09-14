# RAPPORT DE TESTS — CLARTÉ360 GESTION DES ACTIONS — I9-B

Date : 12 septembre 2026

## Résultat

`PYTHONPATH=. pytest -q`

**139 tests réussis / 139**

## Contrôles I9-B ajoutés

- modalités contrôlées par prestation ;
- refus E-learning pour Coaching ;
- conversion du numéro Excel 31364 vers 1985-11-13 ;
- conversion JJ/MM/AAAA et ISO ;
- rejet d'une date ambiguë ;
- rattachement automatique exact d'un bénéficiaire permanent ;
- absence de fusion automatique nom/prénom sans date de naissance ;
- participant ajouté après activation => communication planning en file ;
- contresignature anticipée si tous les statuts sont définitifs ;
- demande de contresignature planifiée à la fin si des statuts restent en attente ;
- accélération de la demande si les statuts deviennent définitifs avant la fin ;
- bornes des offsets calendrier ;
- envoi d'une communication I9 par le worker et passage au statut ENVOYE.

## Compilation

Compilation Python réalisée sur les fichiers principaux après modification.

## VPS

Aucune modification VPS. Aucun déploiement. Aucun secret ajouté au code ou à l'archive.
