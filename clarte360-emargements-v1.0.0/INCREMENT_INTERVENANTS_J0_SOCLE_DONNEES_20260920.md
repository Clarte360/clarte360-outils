# CLARTE360 - Gestion Intervenants - J0 Socle de donnees

Date : 2026-09-20
Socle : clarte360-gestion-actions-v3.0.0-I9-J2C-PIP-LIAISON-I-CRM0-RC2

## Objet
Migration additive du socle identitaire des personnes professionnelles. Aucun changement d'interface et aucun raccordement operationnel de Gestion des Formations a ce jalon.

## Realise
- table `professional_persons` avec identifiant stable `professional_person_id` ;
- liaison 1:1 transitoire avec `trainers.id` ;
- statut principal CANDIDAT / INTERVENANT ;
- sous-etats candidat prevus au CDC ;
- actif/inactif ;
- `supplier_id` reserve pour la future liaison Gestion Clients, sans duplication fournisseur ;
- date de revue de qualification reservee ;
- historique de changement de statut ;
- migration idempotente des intervenants historiques vers une personne professionnelle ;
- conservation de l'etat actif/inactif existant ;
- aucune competence ni qualification inferee lors de la migration ;
- creation d'un `professional_person_id` lors de la creation d'un nouvel intervenant historique.

## Non realise volontairement en J0
Prestations, qualifications, IA, documents professionnels, alertes, nouvelle UX Intervenants et raccordement aux listes operationnelles : jalons suivants.

## Tests
365 tests passes, dont 362 tests du socle RC2 et 3 nouveaux tests J0.
