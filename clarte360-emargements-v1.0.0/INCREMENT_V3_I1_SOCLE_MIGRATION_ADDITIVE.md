# Clarté360 — Gestion des actions V3 — I1

## Périmètre livré

- changement d’identité produit vers **Clarté360 — Gestion des actions** ;
- migration additive, sans suppression de colonnes ou preuves V2 ;
- table `action_trainers` ;
- table `slot_trainers` ;
- table `trainer_assignment_history` ;
- table `action_modules` ;
- migration idempotente des `actions.trainer_id` existants vers un intervenant référent ;
- affectation de cet intervenant aux créneaux V2 existants comme principal ;
- conservation de `actions.trainer_id` pour compatibilité pendant la transition ;
- synchronisation de l’affectation mono-intervenant V2 avec le nouveau socle V3 ;
- synchronisation des quatre modules V2 vers `action_modules` ;
- création des futurs modules V3 en état désactivé ;
- **Teams n’est jamais activé automatiquement**, quelle que soit la modalité de l’action ;
- historique initial des affectations migrées ;
- nouveaux index de support.

## Hors périmètre I1

I1 n’expose pas encore l’interface multi-intervenants, ne modifie pas les règles d’émargement/contresignature, ne sépare pas encore les trois portails et n’intègre pas Microsoft Graph/Teams. Ces sujets appartiennent aux incréments suivants.

## Compatibilité

La migration est additive et idempotente. Les colonnes et tables V2 restent en place. Les preuves historiques ne sont ni modifiées ni supprimées.
