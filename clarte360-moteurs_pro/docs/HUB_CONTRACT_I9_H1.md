# Contrat Hub I9-H1 — Moteurs professionnels

Outil bénéficiaire rattaché à une action existante. Prescription autorisée depuis Gestion des Actions par `admin` ou `intervenant`. Contexte signé HMAC : `tool_id=moteurs-professionnels`, `hub_source`, `beneficiary_id`, `action_id`, `participant_id`, `prescription_id`, `role`, `iat`, `exp`, `scopes`. Scope minimal : `MOTEURS_RUN`.

Le moteur de calcul et les réponses restent la propriété de l'application. Le Hub ne doit recevoir par défaut que l'état technique de prescription/passation. Aucun secret n'est embarqué dans le ZIP.
