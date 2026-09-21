# INCRÉMENT J13 — RECETTE FINALE / VERSION DÉPLOYABLE VPS
Date : 20/09/2026

## Objet
Figer la version issue de J12 comme livraison finale déployable de Gestion des Actions intégrant le module Intervenants / Partenaires.

## Périmètre
Aucune fonctionnalité métier nouvelle.

## Ajustements de livraison
- contrôle du Framework VPS V1.3 ;
- confirmation de la cible existante `https://emargements.clarte360.com` / port 8501 ;
- confirmation du service `clarte360-emargements.service` ;
- conservation du dossier stable `/opt/clarte360/clarte360-outils/clarte360-emargements-v1.0.0/` ;
- correction du fichier systemd du worker afin qu'il utilise le même dossier stable ;
- réécriture de la procédure de déploiement pour une mise à jour de l'application existante ;
- ajout d'une procédure J13 explicite ;
- retrait des caches de développement du package final ;
- contrôle des secrets et fichiers sensibles ;
- non-régression complète : 423/423 tests réussis.

## Décision
Cette version constitue la candidate finale à déployer sur le VPS pour mettre à jour Gestion des Actions / Émargements.
