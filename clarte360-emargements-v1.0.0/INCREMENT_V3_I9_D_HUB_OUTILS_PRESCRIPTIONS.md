# CLARTÉ360 — V3 I9-D
## Hub des outils — catalogue, prescriptions et portail bénéficiaire

Date : 12/09/2026
Base : `clarte360-gestion-actions-v3.0.0-I9-C.zip`

## Objectif
I9-D installe la première couche réellement générique du Hub Clarté360. Gestion des Actions ne recopie aucun moteur métier : elle référence les outils, sait qui peut les prescrire, conserve le contexte bénéficiaire/action, crée un accès Hub temporaire et suit l’état de la prescription.

## Schéma additif
Quatre tables nouvelles sont ajoutées sans modifier les preuves I8/I9 existantes :

- `tool_catalog` : référentiel universel des outils ;
- `tool_prescriptions` : prescriptions par bénéficiaire/action ;
- `prescription_access_tokens` : jetons temporaires dont seule l’empreinte SHA-256 est persistée ;
- `prescription_events` : historique des transitions et préparation de l’idempotence connecteur.

Le champ `action_trainers.can_prescribe_tools` est ajouté avec valeur par défaut `0`.

## Catalogue
Le catalogue supporte : code, nom, catégorie, URL vérifiée, version, actif/inactif, publics autorisés, prestations compatibles, prescription autorisée, type de lancement, durée de validité, règles RGPD, code/état connecteur et métadonnées versionnées.

Seul PIP RIASEC/O*NET est pré-référencé automatiquement car son URL et sa version sont explicitement établies par le CDC I9 V2.0 :

- code : `PIP_RIASEC_ONET` ;
- version : `1.0.7-RC5` ;
- URL : `https://pip-riasec.clarte360.com` ;
- lancement : `EXTERNAL_SIGNED` ;
- connecteur : `PENDING_I9_E`.

I9-D n’invente aucune URL pour les autres applications Clarté360.

## Prescription
Une prescription comporte un identifiant public stable `PRX-*`, l’outil/version, le bénéficiaire permanent, l’action, le participant de contexte, le prescripteur, la temporalité, le statut, les références de résultats et les métadonnées.

États : `A_FAIRE`, `ENVOYE`, `CONSULTE`, `EN_COURS`, `TERMINE`, `A_REVOIR_EN_SEANCE`, `REVU_EN_SEANCE`, `ANNULE`.

## Droits
- Administrateur : prescription autorisée sur un bénéficiaire permanent rattaché à l’action.
- Intervenant : prescription uniquement si `can_prescribe_tools=1` pour l’action.
- Bénéficiaire : visualisation et lancement de ses seules prescriptions.

## Accès sécurisé
Le portail crée un jeton temporaire opaque. Seule son empreinte SHA-256 est conservée en base. Le jeton expire et est à usage unique. La résolution du jeton passe la prescription à `CONSULTE` et ne révèle aucun identifiant de connecteur dans le portail.

Pour un outil générique `HUB_REDIRECT`, le Hub peut ouvrir une URL vérifiée. Pour le PIP RC5, I9-D refuse implicitement de contourner le contrat signé : l’écran informe que le connecteur sécurisé sera activé par I9-E.

## Non-régression
Aucun secret, aucune donnée de production et aucun moteur métier externe n’est inclus. Les tables sont additives. Les fonctions I9-A/B/C restent inchangées.
