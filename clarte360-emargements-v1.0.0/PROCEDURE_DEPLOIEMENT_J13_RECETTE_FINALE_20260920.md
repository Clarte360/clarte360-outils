# J13 — Recette finale / version déployable VPS

## Nature de la livraison

J13 ne crée pas une nouvelle application. Il fige la version finale du module Intervenants / Partenaires intégré à **Gestion des Actions / Émargements**.

## Cible VPS confirmée

- Application : Gestion des Actions / Émargements / I9
- URL : `https://emargements.clarte360.com`
- Port : `8501`
- Service : `clarte360-emargements.service`
- Worker : `clarte360-emargements-worker.service`
- Dossier stable : `/opt/clarte360/clarte360-outils/clarte360-emargements-v1.0.0/`

Aucun nouveau port, sous-domaine ou service n'est réservé.

## Garde-fous de déploiement

- sauvegarde complète avant mise à jour ;
- conservation des données persistantes ;
- secrets uniquement via le mécanisme centralisé VPS ;
- tests complets avant redémarrage ;
- contrôle web + worker + port + URL après redémarrage ;
- recette métier post-déploiement sur les parcours historiques et le nouveau module Intervenants.

## Version de référence

Cette procédure accompagne le package :
`clarte360-gestion-actions-v3.0.0-INTERVENANTS-J13-RECETTE-FINALE-VPS.zip`
