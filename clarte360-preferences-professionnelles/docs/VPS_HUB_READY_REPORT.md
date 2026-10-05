# État VPS / Hub — Préférences professionnelles 1.9.7

## VPS
- URL cible : `https://preferences-professionnelles.clarte360.com` (préparée, non déployée).
- Service proposé : `clarte360-preferences-professionnelles.service`.
- Port interne réservé : `8507`, binding `127.0.0.1`.
- Point d'entrée : `app.py`.
- Environnement Python dédié `.venv`.
- Secrets : SMTP et HMAC Hub hors Git via `.streamlit/secrets.toml`.
- Aucun worker nécessaire.
- Données métier historiques : le JSON reste exportable/importable. Si une persistance serveur est ajoutée lors du branchement Hub, elle devra être placée hors zone écrasée par `git pull`.

## Reverse proxy futur
DNS `preferences-professionnelles.clarte360.com` -> VPS, proxy HTTPS vers `127.0.0.1:8507`, certificat TLS géré côté proxy.

## Mise à jour
Développement -> tests -> GitHub -> VPS -> tests VPS -> compilation -> redémarrage -> recette métier, conformément au Framework VPS Clarté360.

## Rollback
Retour au commit précédent pour le code ; les éventuelles données persistantes Hub/exports ne doivent jamais être rollbackées par Git.

## Hub I9-H1
L'application reste autonome et peut également être prescrite à un bénéficiaire d'une action existante par Administrateur ou Intervenant. Le contrat signé est décrit dans `docs/HUB_CONTRACT_I9_H1.md`.

## Identité VPS figée au Jalon 3
- `tool_id` : `preferences-professionnelles`.
- URL officielle : `https://preferences-professionnelles.clarte360.com`.
- Port interne : `8507` (réservé par le registre central Framework VPS ; ne pas utiliser `8514`, réservé à Compétences / Projets).
- Service systemd : `clarte360-preferences-professionnelles.service`.
- Dossier stable : `/opt/clarte360/clarte360-outils/clarte360-preferences-professionnelles/`.
- Référence de contrôle : Framework VPS Clarté360 V1.4, registre central.
