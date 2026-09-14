# Audit global PIP RIASEC / O*NET — 1.0.8

## Décision

Application déjà VPS, architecture métier préservée. Cette livraison est une consolidation **validation des saisies + VPS + Hub ready**, sans déploiement.

## Risques traités

1. Saisies publiques trop permissives (identité, téléphone, e-mail, textes).
2. Reprise JSON pouvant contourner des règles d’interface.
3. IDs techniques réutilisés dans chemins/événements.
4. Contrat Hub hétérogène entre ancien champ `rights` et futur vocabulaire `scopes`.
5. Identité/URL de l’application non centralisée dans un artefact versionné.
6. Documentation des secrets incomplète (SMTP absent du fichier d’exemple).

## Garanties de non-régression

- 61 tests initiaux conservés et adaptés uniquement lorsque la nouvelle validation rendait volontairement invalide un ancien exemple de test (`phone="1"`).
- 42 tests supplémentaires.
- 103/103 tests réussis.
- Banque PIP, scoring, code Holland, O*NET et parcours inchangés.

## Données persistantes à protéger

- `accompanied_runs/`
- `connector_outbox/`
- `public/leads/`
- `public/study/`
- futurs rapports/exports sous le répertoire configuré par `CLARTE360_PIP_DATA_DIR`.

## Secrets attendus

- `ONET.ONET_API_KEY`
- `ONET.ONET_API_BASE_URL` (non secret mais configurable)
- `PIP_CONNECTOR.LAUNCH_SIGNING_KEY`
- `email.smtp_server`
- `email.smtp_port`
- `email.smtp_user`
- `email.smtp_password`
- `email.from_email`
- `email.to_email`

Aucune valeur réelle n’est incluse dans le ZIP.

## Réserves avant déploiement réel

- Vérifier le port actuellement utilisé par le service PIP de production avant toute modification systemd/reverse proxy.
- Sauvegarder les données persistantes actuelles avant toute éventuelle migration vers `/opt/clarte360/data/pip-riasec-onet`.
- Recetter le jeton réellement produit par I9-H1 et la consommation des événements outbox/callback.
- Exécuter la suite dans le `.venv` VPS réel avant redémarrage.
