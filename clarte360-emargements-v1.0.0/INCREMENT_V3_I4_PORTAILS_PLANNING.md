# CLARTÉ360 — GESTION DES ACTIONS V3
## Incrément I4 — Portails séparés + gestion du planning

Version : **3.0.0-I4** — cumulative **I1 + I2 + I3 + I4**.

## Portes d'entrée
- La racine historique reste l'accès Administration et affiche désormais explicitement « Clarté360 — Gestion des actions — Administration ».
- L'écran de connexion Administration ne contient plus aucun bouton vers l'espace intervenant ou bénéficiaire.
- L'accès intervenant reste stable via `?trainer_portal=1`.
- L'accès bénéficiaire reste stable via `?beneficiary_portal=1`.
- Les anciens liens d'invitation/réinitialisation restent compatibles.

## Droits de planning intervenant
Deux niveaux additifs sont introduits :
- `action_trainers.can_manage_planning` : gestion du planning de l'action ;
- `slot_trainers.can_manage_planning` : modification d'un créneau explicitement autorisé.

Ces droits sont accordés depuis l'onglet Administration > Intervenants. La simple visibilité d'une action ou d'un créneau ne donne jamais un droit de modification.

## Garde-fous serveur
Toute modification du planning par un intervenant est contrôlée côté service :
- action clôturée/archivée interdite ;
- séance déjà terminée interdite en modification directe ;
- preuve historique existante interdite ;
- respect des bornes de l'action ;
- absence de chevauchement ;
- absence de conflit horaire d'un intervenant affecté ;
- conservation de la durée d'un créneau existant ;
- ajout impossible s'il dépasse le volume contractuel ;
- un intervenant limité à un créneau ne peut pas modifier une co-animation impliquant un autre intervenant sans droit action.

## Synchronisation
Chaque changement validé crée une trace `planning_change_events` et synchronise les éléments déjà implémentés :
- vues Administration / Intervenant / Bénéficiaire : données communes en base ;
- échéances d'émargement PENDING recalculées ;
- campagnes qualité PENDING recalculées ;
- journal d'audit ;
- notifications des participants et intervenants concernés lorsque l'action est active et que le mail est disponible.

Le hook Teams est enregistré mais reste volontairement `NOT_ENABLED` ou `PENDING_I7` : I4 ne crée aucun objet Microsoft et ne préjuge pas de l'architecture Graph du lot I7.

## Calendriers ICS
Les espaces Intervenant et Bénéficiaire proposent un export ICS avec identifiants stables par créneau :
`clarte360-slot-<id>@gestion-actions`.

Un créneau reporté/annulé est publié avec `STATUS:CANCELLED`, ce qui permet de conserver une identité stable lors d'une actualisation de calendrier.

## Compatibilité
- aucune suppression de table ou colonne V2/I1/I2/I3 ;
- aucune modification des preuves historiques ;
- chemins VPS, URL, services et secrets inchangés ;
- Teams toujours non activé automatiquement.
