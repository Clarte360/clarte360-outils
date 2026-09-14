# Contrat Hub I9-H1 — Contractualisation

## Positionnement impératif
Contractualisation est un **outil de gestion interne**. Il n'est jamais destiné à être ouvert par un bénéficiaire et ne doit jamais générer une invitation bénéficiaire.

- rôle autorisé : `admin` ;
- rôle `beneficiaire` : refusé ;
- le bénéficiaire transmis par le Hub est uniquement le **sujet du dossier** à contractualiser ;
- l'application reste utilisable de manière autonome avec son authentification administrative existante.

## Lancement Hub prévu
Contexte minimal : `tool_id`, `hub_source=GESTION_ACTIONS_I9`, `role`, `action_id`, `beneficiary_id` si un dossier est ciblé, `participant_id` si disponible, `prescription_id` si le Hub crée une prescription interne, `expires_at`, `scopes`.

Le contexte doit être signé HMAC. Le secret reste exclusivement dans les secrets du VPS.

Scopes recommandés : `contractualisation:read_action`, `contractualisation:prepare`, `contractualisation:export`. Aucun scope d'accès bénéficiaire.

## Retours Hub
Uniquement des statuts administratifs minimisés : `opened`, `draft`, `generated`, `exported`, `error`, avec `action_id`, `prescription_id` et `no_clar` si disponible. Aucun PDF contractuel ni donnée financière détaillée ne remonte automatiquement au Hub sans décision métier ultérieure.

## Données métier préservées
La base XLSM reste chargée en lecture seule. Les exports CONV ADM + FINANCEMENTS, JSON, PDF et ZIP de session restent sous le contrôle de l'utilisateur administratif. Le futur connecteur ne doit pas remplacer la macro locale ni réécrire le classeur source.
