# Clarté360 — Gestion des Actions V3.0.0-I9-E
## Connecteur PIP RIASEC / O*NET RC5

Date : 12/09/2026
Base : V3.0.0-I9-D

## Objectif

Brancher le premier outil réel au Hub générique I9-D sans dupliquer le PIP dans Gestion des Actions. Le PIP reste propriétaire de son moteur, de sa persistance et de ses résultats ; Gestion des Actions devient l'orchestrateur de prescription, lancement et suivi.

## Contrat de lancement implémenté

Le contrat est strictement celui du code réel PIP RC5 :

- URL : `https://pip-riasec.clarte360.com/?mode=accompagnement&launch=<TOKEN>` ;
- jeton : `base64url(canonical-json).base64url(HMAC-SHA256(payload_part))` ;
- données : `beneficiary_id`, `action_id`, `participant_id` optionnel, `prescription_id`, `rights`, `iat`, `exp`, `v` ;
- durée maximale compatible RC5 : 7 jours ; I9-E utilise 15 minutes pour le lancement depuis le Hub ;
- aucune donnée nominative n'est embarquée dans le jeton ;
- clé partagée attendue dans le secret VPS `pip_connector.launch_signing_key`.

## Synchronisation retour PIP → Hub

RC5 publie actuellement dans son outbox durable les événements :

- `CONSULTE` ;
- `EN_COURS` ;
- `TERMINE`.

I9-E lit cette outbox de façon idempotente et met à jour la prescription correspondante. Avant toute mutation, les identifiants bénéficiaire/action/participant/prescription sont comparés aux données du Hub. Un événement incohérent est rejeté et le curseur n'avance pas.

La source RC5 actuelle fournit aussi `passation_id` et `app_version` : ces références sont conservées. Elle ne publie pas dans l'outbox de scores RIASEC, détail de réponses ou livrables ; I9-E n'invente donc aucune donnée supplémentaire.

## Robustesse

- curseur persistant dans `connector_cursors` ;
- lecture par offset binaire ;
- ligne partiellement écrite non consommée ;
- troncature/rotation gérée par reprise à zéro avec idempotence DB ;
- event ID déterministe par hash de la ligne source ;
- synchronisation PIP exécutée même lorsque SMTP est désactivé ;
- erreurs PIP isolées des autres modules ;
- aucun détail technique exposé au bénéficiaire.

## Configuration VPS à prévoir lors de la recette finale

```toml
[pip_connector]
launch_signing_key = "<SECRET_PARTAGE_AVEC_PIP>"
outbox_path = "<CHEMIN_REEL_VPS_VERS_gestion_actions_events.jsonl>"
```

Les valeurs réelles ne doivent jamais être versionnées ni ajoutées au ZIP.

## Fichiers principaux impactés

- `pip_connector.py` — contrat HMAC + parser/lecteur outbox ;
- `services.py` — lancement PIP, consommation idempotente, statut runtime ;
- `db.py` — migration additive `connector_cursors` ;
- `worker.py` — traitement automatique de l'outbox ;
- `app.py` — ouverture PIP depuis la prescription ;
- `tests/test_v3_i9e_pip_connector.py` — tests I9-E.

## Résultat

165 tests réussis sur 165. Compilation Python complète OK.
