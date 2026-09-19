# Rapport — Liaison PIP / Gestion des Actions — Jalon C

Version : `3.0.0-I9-J2C-PIP-LIAISON-C-CALLBACK`
Date : 2026-09-18
Base : jalon B `3.0.0-I9-J2C-PIP-LIAISON-B-IDEMPOTENCE-SECURITE`.

## Réalisé
- Demande de rappel PIP PUBLIC rattachée au contact CRM existant par email normalisé.
- Activité CRM `CALLBACK_REQUESTED` datée : « Demande à être recontacté(e) — PIP-RIASEC PUBLIC — [date/heure] ».
- Mise à jour de l'activité du contact via `updated_at`.
- File dédiée `crm_callback_notifications`, idempotente par `external_event_id`, avec statut, tentatives, erreur et date d'envoi.
- Worker : envoi vers l'adresse interne configurée `[pip_public].callback_email` (fallback adresse d'envoi existante).
- Contenu de l'email limité aux données commerciales autorisées : prénom, nom, email, téléphone, fonction, entreprise, demande, date/heure.
- Aucune réponse PIP, score, code Holland, donnée O*NET, rapport ou pseudonyme d'étude.
- Aucun changement Calendar/Teams et aucun changement du programme PIP.

## Tests
23 tests ciblés A+B+C+CRM+contrat RC8 : PASS.
Compilation Python de `db.py`, `services.py`, `worker.py` : PASS.
