# Contrat d’intégration Hub — PIP RIASEC / O*NET

| Clé | Valeur |
|---|---|
| tool_id | `pip-riasec-onet` |
| nom | PIP RIASEC / O*NET Clarté360 |
| catégorie | Orientation / intérêts professionnels |
| URL | `https://pip-riasec.clarte360.com` |
| lancement autonome | Oui, mode PUBLIC |
| lancement Hub | Oui, mode ACCOMPAGNEMENT par jeton HMAC |
| bénéficiaire | Oui |
| intervenant | Prescrit depuis Gestion des Actions ; pas d’accès direct aux réponses par défaut |
| administrateur | Prescription/gestion côté Hub |
| reprise | Oui, serveur par prescription en mode accompagné |
| expiration | Oui, `exp` signé ; max 7 jours au niveau PIP |
| persistance | VPS, hors Git |
| retour | outbox statut minimale |
| HMAC | Oui |

## Données reçues du Hub

Obligatoires : `beneficiary_id`, `action_id`, `prescription_id`, `iat`, `exp`, scope `PIP_RUN`.

Optionnelles : `participant_id`, `tool_id`, `hub_source`, `return_mode`, scopes complémentaires.

Aucune identité civile n’est exigée dans l’URL : Gestion des Actions reste source de vérité de l’identité.

## Données retournées par défaut

Identifiants techniques, `passation_id`, version applicative, événement et timestamp. Pas de coordonnées personnelles et pas de réponses détaillées dans l’outbox standard.

## RGPD

Minimisation stricte. Les réponses et résultats restent dans l’application PIP. Toute future remontée de résultat/livrable vers le Hub doit être couverte par un scope explicite et une règle de visibilité définie.
