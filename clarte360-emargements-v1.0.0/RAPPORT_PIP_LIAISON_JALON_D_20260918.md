# Rapport — Jalon D liaison PIP — 2026-09-18

Base : `3.0.0-I9-J2C-PIP-LIAISON-C-CALLBACK`.

## Objet
Enrichir le lancement ACCOMPAGNEMENT avec quatre informations d’affichage prévues par le CDC, sans modifier le mécanisme d’autorisation.

## Réalisation
- `beneficiary_first_name`
- `beneficiary_last_name`
- `action_number`
- `action_title`

Ces champs sont inclus dans le payload signé HMAC-SHA256. Les identifiants techniques, les quatre droits RC8, `v=1`, `iat/exp`, l’URL de lancement et le secret existant restent inchangés.

Le constructeur bas niveau reste rétrocompatible : si les champs d’affichage ne sont pas fournis, ils sont omis.

## Hors périmètre
Aucun changement Calendar/Teams, aucun changement du programme PIP, aucun gel du futur contrat d’événements, aucun résultat ou réponse PIP/O*NET dans le token.
