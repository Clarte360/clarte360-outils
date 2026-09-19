# Rapport Jalon H — Intégration finale avec PIP

- Base : Jalon G.
- PIP parallèle audité : Jalon E1 du 18/09/2026.
- Jeton ACCOMPAGNEMENT aligné avec le vocabulaire réellement accepté par PIP E1 (`rights` + `scopes`, `tool_id`, `hub_source`, `return_mode`).
- Consommation des événements ACCOMPAGNEMENT E1 centralisée et rétrocompatible.
- Contrat PUBLIC figé pour `CONTACT_EMAIL_VERIFIED`, `CONTACT_UPDATED`, `CALLBACK_REQUESTED`, avec séparation CRM/étude et idempotence.
- Enveloppe HMAC serveur-à-serveur documentée et prise en charge.
- Rapports documentaires : support `PIP_REPORT` + `ONET_REPORT`, sans silo.
- Chemins d’exemple `outbox_path` / `study_dir` alignés sur la structure persistante PIP E1.
- Aucune modification du programme PIP, de Calendar ou de Teams.
- Limite connue : PIP E1 n’émet pas encore les événements PUBLIC signés ni le flux automatique de rapport ; ce point appartient au chantier PIP parallèle.
