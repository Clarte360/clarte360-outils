# Migrations C&P

GO-19 crée le schéma initial `1`. Toute évolution ultérieure doit être additive, versionnée et testée. Aucune migration destructive sans sauvegarde préalable et décision explicite.


## GO22 RC2 - Migration additive vers schema 3

La version 3 ajoute trois tables : `preparation_states`, `preparation_questionnaires`, `preparation_responses`. Les snapshots Q et R sont append-only et protégés par quatre triggers SQLite refusant UPDATE/DELETE ; la table d'état utilise un contrôle `row_version` optimiste. Les tables historiques `cases`, `phase_states`, `career_items` et autres tables du schéma 1 restent intactes ; les tables d'orientation du schéma 2 restent intactes. Cette migration a été vérifiée sur une base de démonstration GO21 RC2, jamais sur une base production. Sauvegarde, arrêt de la session, migration et restauration doivent être testés sur environnement isolé avant toute autorisation VPS.


## GO23-1 — Migration additive vers schema 9

La version 9 ajoute le lien optionnel d’une mission hors séance à un métier ROME (`job_target_id`). Les anciennes missions et réponses restent présentes ; les liens historiques ne sont pas devinés. Cette migration locale ne constitue pas une migration production. Avant tout déploiement : sauvegarde restaurable, migration sur copie isolée, puis contrôle métier et technique.
