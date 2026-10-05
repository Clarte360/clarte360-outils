# Contrat Hub I9-H1 — Préférences professionnelles

Préférences professionnelles est un outil **bénéficiaire** utilisé dans une action déjà créée. La prescription peut être initiée depuis Gestion des Actions par un **Administrateur** ou un **Intervenant**. Le bénéficiaire reçoit un lien sécurisé et réalise lui-même le questionnaire.

Contexte signé attendu : `tool_id=preferences-professionnelles`, `hub_source`, `role`, `beneficiary_id`, `action_id`, `participant_id`, `prescription_id`, `iat`, `exp`, `scopes`.

Scope obligatoire : `PREFERENCES_RUN`. Scopes possibles : `PREFERENCES_RESUME`, `PREFERENCES_STATUS`, `PREFERENCES_DOCUMENT_READ`.

Retour Hub minimal : statut (`opened`, `in_progress`, `completed`, `error`, `expired`) et, si disponible, une référence de document. Les réponses question par question, scores détaillés et données de traçabilité ne sont pas injectés automatiquement dans Gestion des Actions.

Le questionnaire reste propriétaire de son métier : ordre aléatoire, 60 questions, scoring, dix dimensions et interprétation ne sont pas modifiés par le connecteur.

Le JSON historique produit par la version Streamlit Cloud 1.9.4 reste le format de reprise à préserver. La validation ajoutée en 1.9.5 accepte les JSON conformes 1.9.4 et bloque les structures incohérentes ou dangereuses.

Réserve de recette : le branchement effectif au mécanisme d'invitation/callback I9-H1 devra être testé en recette croisée au moment du déploiement VPS ; le présent ZIP prépare le contrat mais ne déploie rien.
