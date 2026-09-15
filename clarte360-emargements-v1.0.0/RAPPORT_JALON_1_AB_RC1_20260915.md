# CLARTÉ360 — Gestion des Actions I9 — JALON 1 A+B — RC1

Date : 15 septembre 2026  
Socle de départ : `clarte360-gestion-actions-v3.0.0-I9-H2.8-ROBUSTESSE-UX-QUALITE-OUTILS-CLEAN`  
Version candidate : `3.0.0-I9-J1-AB-RC1`

## 1. Principe

Le développement a été réalisé exclusivement à partir du socle H2.8. Les évolutions sont additives et conservent l'architecture existante. Aucun moteur externe Clarté360 n'a été recopié dans Gestion des Actions.

## 2. Bloc A — consolidation

### Outils Clarté360
- ajout d'une écriture atomique de la sélection complète des outils autorisés par action ;
- relecture de la vérité DB après rerun/F5 ;
- contrôle serveur du droit `can_prescribe_tools` pour une prescription initiée par un intervenant ;
- conservation de la protection anti-doublon actif ;
- conservation de l'annulation par le créateur ;
- ajout d'une annulation explicite par supervision ADMIN avec audit dédié.

### Documents
- ajout additif des métadonnées `origin`, `regulatory`, `immutable_reason` ;
- conservation SHA-256, auteur, date, action et bénéficiaire ;
- dépôts multiples dans les interfaces ADMIN et INTERVENANT ;
- PDF/JSON restent autorisés ;
- blocage serveur de la suppression standard d'une preuve marquée réglementaire/protégée ;
- affichage ADMIN de l'origine, de la date et de l'état de protection.

### Teams — terminologie de preuve
- remplacement des formulations pouvant laisser entendre une absence par `Rapprochement non établi` lorsque le rapport Graph existe mais que l'identité n'est pas rapprochée.

## 3. Bloc B — séances, Teams et communications

Les fonctions déjà présentes en H2.8 sont conservées : multi-intervenants, affectations par créneau, salle Teams stable, occurrences, Graph, preuves, émargements, statuts de présence, régularisation, contresignatures et neutralisation des demandes futures.

### Rappels Teams H-2 / H-15
- création de deux événements idempotents par destinataire et créneau ;
- destinataires : chaque bénéficiaire actif + chaque intervenant/coanimateur réellement affecté au créneau ;
- source intervenants : affectations `slot_trainers` ;
- recalcul des rappels non envoyés après changement de calendrier ;
- neutralisation des rappels des créneaux annulés/reportés/remplacés ;
- aucun rappel n'est envoyé après le début du créneau ;
- email bénéficiaire : lien Teams + espace bénéficiaire + rappel d'activation si nécessaire ;
- email intervenant : lien Teams + espace intervenant ;
- traçabilité et idempotence via `communication_events`.

## 4. Migrations

Migrations additives uniquement :
- `document_references.origin` ;
- `document_references.regulatory` ;
- `document_references.immutable_reason`.

`init_db()` reste idempotent. Aucune table ou donnée historique n'est supprimée ou réinitialisée.

## 5. Tests

Baseline H2.8 avant modification : **290 passed**.

Après Jalon 1 : **296 passed**.

`release_check.py` : **CANDIDATE TECHNIQUE OK**.

Compilation : `db.py`, `services.py`, `worker.py`, `app.py`, `branding.py` — OK.

Tests ajoutés notamment :
- persistance atomique de 3 outils ;
- droit de prescription intervenant contrôlé côté service ;
- annulation ADMIN auditée ;
- métadonnées documentaires et preuve non supprimable ;
- H-2/H-15 pour bénéficiaire + animateur + coanimateur ;
- idempotence des rappels ;
- recalcul après déplacement ;
- neutralisation après annulation ;
- contenu des emails Teams ;
- migration documentaire idempotente ;
- vocabulaire Teams non assimilable à une absence.

## 6. État

Cette RC1 est prête pour la recette navigateur ciblée du Jalon 1 avant tout PUSH GitHub/VPS.
