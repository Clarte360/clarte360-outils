# Rapport de tests - Jalon H3 - 2026-09-19

Base : Jalon H2 officiel OneDrive.

## Suite complète
- 190 tests exécutés
- 190 réussis
- 0 échec

## Recettes spécifiques H3
- CONTACT_EMAIL_VERIFIED : payload commercial accepté sans clé de jonction.
- CONTACT_UPDATED : même garde-fou de séparation.
- CALLBACK_REQUESTED : coordonnées/reason/requested_at autorisés, aucune clé de recherche.
- Chaque clé interdite CRM est refusée par le connecteur PIP, y compris imbriquée.
- `participant_id` absent des builders CRM dans `pages.py`.
- Dataset étude : schema exact `clarte360.pip.public-study.v1`.
- Dataset étude : `study_id` présent, non vide et indépendant pour deux sessions neuves.
- Dataset étude : aucune identité, aucun participant/passation/contact/CRM id ou source_ref.
- Absence de consentement étude : aucun fichier de recherche créé.
- Outbox active unique : `data/connector_outbox/gestion_actions/events.jsonl`.
- Correctif H2 rapport -> ressenti conservé.

## Contrôles complémentaires
- `scripts/check_sources.py` : OK.
- `scripts/build_pip_runtime.py --check` : OK.
- `scripts/build_interpretation_runtime.py --check` : OK.
- `scripts/build_rome_runtime.py --check` : OK (1911 fiches).
- `python -m compileall -q app.py clarte360_pip` : OK.

## Limite volontaire
Aucune recette réelle Gestion des Actions/VPS n'est déclarée ici : H3 n'est pas déployé. La recette réelle PUBLIC de bout en bout doit être rejouée après push puis déploiement contrôlé.
