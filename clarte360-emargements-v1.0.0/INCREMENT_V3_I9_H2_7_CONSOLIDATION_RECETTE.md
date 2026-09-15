# I9-H2.7 — Consolidation recette réelle

- Correction du dernier appel `time(12,0)` dans Suivi/Rattrapage : `dt_time(12,0)`.
- Les demandes de contresignature ne sont plus précréées pour les créneaux futurs avec participants en attente.
- Les anciennes demandes futures créées par H2.4/H2.6 sont automatiquement annulées avant envoi.
- Une demande est créée immédiatement si tous les statuts participants sont définitifs avant la fin, sinon à la fin du créneau.
- L'administration ne compte plus les créneaux futurs comme « contresignatures attendues ».
- Teams : les séances futures sont affichées comme « réunion planifiée » ; le statut « rapport en attente » n'est utilisé qu'une fois la séance échue.
- Conservation des preuves Teams détaillées, rapports techniques, rapprochement manuel et isolation des données techniques côté administrateur.
