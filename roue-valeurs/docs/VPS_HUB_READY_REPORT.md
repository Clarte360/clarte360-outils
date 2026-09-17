# VPS / Hub Ready — Roue des valeurs

URL cible : `https://roue-valeurs.clarte360.com` (non déployée).
Service proposé : `clarte360-roue-valeurs.service`.
Port interne proposé : **8514**, binding `127.0.0.1`.
Secrets attendus : SMTP, `security.energy_access_code`, `security.hub_hmac_secret`.
Aucun secret réel n'est inclus dans le ZIP.

L'application ne requiert pas de worker. Les réponses bénéficiaire restent principalement sous le contrôle du bénéficiaire via JSON. Les éventuels journaux/outbox/statuts Hub devront utiliser un répertoire persistant hors zone écrasée par Git lors du déploiement.

Cycle futur : tests local -> GitHub -> `git pull` VPS -> `.venv`/requirements -> pytest -> compilation -> restart systemd -> recette métier. Aucun déploiement n'est effectué dans ce livrable.
