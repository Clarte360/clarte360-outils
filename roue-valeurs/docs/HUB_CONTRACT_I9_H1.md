# Contrat Hub I9-H1 — Roue des valeurs

- `tool_id`: `roue-valeurs`
- URL cible: `https://roue-valeurs.clarte360.com`
- Prescripteurs autorisés: **Administrateur, Intervenant**.
- Utilisateur final: **bénéficiaire** rattaché à une action existante.
- Identifiants requis: `beneficiary_id`, `action_id`, `participant_id`, `prescription_id`.
- Lancement: lien temporaire signé HMAC, expiration maximale 7 jours.
- Scopes: `ROUE_VALEURS_RUN`, `ROUE_VALEURS_STATUS`, éventuellement `ROUE_VALEURS_DOCUMENT_READ`.
- L'application reste utilisable de façon autonome et conserve l'import des JSON issus de la version Streamlit Cloud.
- Retour Hub minimal: `opened`, `in_progress`, `completed`, `error`, références métier et éventuelle référence documentaire. Les réponses détaillées, exemples, valeurs et commentaires ne sont pas renvoyés automatiquement au Hub.
- L'activation de « Valeurs énergies » reste une décision d'accompagnement et son code est un secret VPS/Streamlit, jamais un secret inclus dans l'URL Hub.
