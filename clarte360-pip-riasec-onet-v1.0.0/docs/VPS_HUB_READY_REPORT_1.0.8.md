# PIP RIASEC / O*NET — État VPS + Hub I9-H1

## VPS

L’application est déjà opérationnelle sur le VPS à :

`https://pip-riasec.clarte360.com`

Cette livraison **ne doit pas être déployée automatiquement**. Elle prépare/contrôle le ZIP source.

### Code / secrets / données

- Code : dossier stable `clarte360-pip-riasec-onet-v1.0.0/`.
- Environnement : `.venv/` propre à l’application.
- Secrets : jamais versionnés ; O*NET, SMTP et clé HMAC restent dans le coffre VPS.
- Ressources versionnées : `resources/`.
- Données d’exécution : `CLARTE360_PIP_DATA_DIR`; défaut local `data/` ignoré par Git.
- Outbox Hub : `<PERSISTENT_DATA_DIR>/connector_outbox/gestion_actions_events.jsonl`.
- Passations accompagnées : `<PERSISTENT_DATA_DIR>/accompanied_runs/`.
- Leads/étude publics : `<PERSISTENT_DATA_DIR>/public/`.

### Port

Le fichier d’identité réserve **8502 comme valeur proposée**, mais la version étant déjà en production, **le port réellement utilisé par le service VPS doit être vérifié avant toute modification du service**. Aucun changement VPS n’est demandé par ce livrable.

### Health check

Streamlit : `/_stcore/health` sur l’interface locale du service.

## Hub Gestion des Actions I9-H1

Le connecteur PIP existant est conservé :

`https://pip-riasec.clarte360.com/?mode=accompagnement&launch=<JETON>`

Le jeton HMAC existant reste compatible. Cette livraison accepte en plus le vocabulaire commun Hub (`tool_id`, `hub_source`, `scopes`, `return_mode`) sans casser les anciens jetons utilisant `rights`.

### Lancement cible

```json
{
  "v": 2,
  "tool_id": "pip-riasec-onet",
  "hub_source": "GESTION_ACTIONS_I9_H1",
  "beneficiary_id": "BEN-...",
  "action_id": "CLA...",
  "participant_id": "PART-...",
  "prescription_id": "PRESC-...",
  "iat": 1800000000,
  "exp": 1800003600,
  "scopes": ["PIP_RUN", "PIP_RESUME", "PIP_STATUS"],
  "return_mode": "OUTBOX"
}
```

### Scopes PIP autorisés

- `PIP_RUN`
- `PIP_RESUME`
- `PIP_STATUS`
- `PIP_RESULT_READ`

`PIP_RUN` est obligatoire pour lancer l’outil.

### Événements retournables

- `CONSULTE`
- `EN_COURS`
- `TERMINE`
- `ERREUR`

Le PIP reste propriétaire des réponses et du scoring. Le Hub ne reçoit par défaut que les identifiants techniques et le statut. Un accès au résultat ne devra être ajouté que si le scope et la règle RGPD correspondants sont explicitement décidés.

## Réserve de recette

L’archive I9-H1 est la référence fonctionnelle du Hub. Le connecteur PIP est prêt côté application ; la recette réelle devra confirmer côté I9-H1 la génération du jeton, les scopes retenus, l’expiration et la consommation de l’outbox/callback avant activation en production.
