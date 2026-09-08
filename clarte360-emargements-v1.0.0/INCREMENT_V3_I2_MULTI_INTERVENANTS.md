# CLARTÉ360 — GESTION DES ACTIONS V3
## Incrément I2 — Multi-intervenants

**Base cumulative :** V3.0.0-I1 + I2  
**Date :** 05 septembre 2026

## Objet

Faire évoluer le socle additif I1 vers une gestion opérationnelle de plusieurs intervenants par action et par créneau, sans supprimer les champs V2 de compatibilité ni réécrire les preuves historiques.

## Réalisé

- plusieurs intervenants actifs sur une même action via `action_trainers` ;
- notion unique d'intervenant référent conservée pour la coordination et synchronisée avec `actions.trainer_id` ;
- plusieurs intervenants actifs sur un même créneau via `slot_trainers` ;
- rôles de créneau `PRINCIPAL`, `CO_INTERVENANT`, `REMPLACANT` ;
- ajout, retrait et remplacement d'une affectation sans suppression de l'historique ;
- lien `replaced_assignment_id` conservant l'affectation remplacée ;
- historique détaillé dans `trainer_assignment_history` ;
- portail intervenant autorisé à partir des affectations V3, avec visibilité limitée aux créneaux réellement affectés ;
- une affectation ponctuelle sur un créneau suffit à donner accès à l'action concernée ;
- les reports et rattrapages recopient les affectations actives du créneau source ;
- un nouveau créneau ordinaire hérite du référent comme principal, les co-intervenants restant des affectations explicites ;
- interface Administration : nouvel onglet **Intervenants** dans une action pour gérer action, créneaux, co-animation et remplacements ;
- suppression physique d'un intervenant désormais refusée lorsqu'il possède des affectations ou preuves historiques ;
- compatibilité V2 maintenue : `assign_trainer()` continue à piloter le référent sans effacer les autres intervenants I2.

## Hors périmètre volontaire I2

- nouvelle contresignature multi-intervenants ;
- blocage temporel de contresignature ;
- signature graphique intervenant ;
- suppression des relances automatiques d'émargement ;
- refonte des trois portes d'entrée ;
- droits de modification de planning par intervenant ;
- Teams / Microsoft Graph.

Ces points relèvent des incréments I3 et suivants.
