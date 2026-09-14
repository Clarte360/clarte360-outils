# Contrat Hub I9-H1 — Boussole des valeurs

La Boussole est un outil bénéficiaire utilisé dans une action déjà créée. La prescription peut être initiée depuis Gestion des Actions par un **Administrateur** ou un **Intervenant**. Le bénéficiaire n'est pas un prescripteur : il reçoit le lien signé et réalise son travail.

Contexte signé attendu : `tool_id=boussole-valeurs`, `hub_source`, `role`, `beneficiary_id`, `action_id`, `participant_id`, `prescription_id`, `iat`, `exp`, `scopes`. Scope obligatoire : `BOUSSOLE_RUN`. Scopes réservés : `BOUSSOLE_RESUME`, `BOUSSOLE_STATUS`, `BOUSSOLE_DOCUMENT_READ`.

Retour minimal : statut technique (`opened`, `in_progress`, `completed`, `error`) et référence documentaire éventuelle. Les exemples, commentaires, cotations et réponses détaillées restent la propriété métier de la Boussole et ne sont pas injectés automatiquement dans Gestion des Actions.

Réserve de recette : le ZIP I9-H1 de Gestion des Actions n'a pas pu être extrait dans l'environnement de construction. Le contrat devra être vérifié en recette croisée avant déploiement.
