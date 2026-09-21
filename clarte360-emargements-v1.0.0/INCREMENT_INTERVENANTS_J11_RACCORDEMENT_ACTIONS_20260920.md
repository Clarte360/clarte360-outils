# J11 — Raccordement Intervenants / Formation / Actions

Date : 20/09/2026

## Objet
Raccorder le référentiel professionnel construit en J0–J10 aux affectations opérationnelles de Gestion des Actions sans casser les structures historiques `trainers`, `action_trainers` et `slot_trainers`.

## Réalisation
- Ajout d'une exigence de prestation par action via `action_service_requirements`.
- Choix de la prestation Clarté360 réellement réalisée, niveau humain minimum 0–4 et option d'exigence de complétude des critères obligatoires.
- Affectation depuis le dossier stable `professional_person_id`, avec pont contrôlé vers le `trainer_id` historique nécessaire aux portails, émargements, contresignatures, Teams, planning et prescriptions.
- Contrôle d'éligibilité fondé sur le statut INTERVENANT actif et la qualification humaine. Les propositions IA ne rendent jamais une personne affectable.
- Les candidats restent non affectables.
- Exception administrative possible uniquement avec justification explicite et audit dédié ; elle ne modifie jamais la qualification humaine.
- Si une action historique n'a pas encore de prestation rattachée, le fonctionnement reste compatible et l'état est signalé `A_VERIFIER` afin d'éviter une rupture lors de la migration.
- Les affectations action et créneau conservent les mécanismes historiques et leur traçabilité.

## Garde-fous
Aucune migration destructive. Aucun renommage des tables historiques. Aucun écrasement des affectations existantes. Le référentiel professionnel devient la porte d'entrée métier, tandis que les identifiants techniques historiques restent utilisés en compatibilité interne.
