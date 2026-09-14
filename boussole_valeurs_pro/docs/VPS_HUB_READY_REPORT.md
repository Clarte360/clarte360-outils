# Préparation VPS / Hub — Boussole des valeurs v1.8.3

URL cible : `https://boussole-valeurs.clarte360.com` — **planned**, non déclarée comme active.

Dossier stable recommandé : `/opt/clarte360/clarte360-outils/clarte360-boussole-valeurs/`. Service : `clarte360-boussole-valeurs.service`. Environnement Python propre `.venv`. Secrets SMTP et secret HMAC Hub dans `.streamlit/secrets.toml` sur VPS, jamais dans Git/ZIP de production. Le code d'accès Valeurs énergies actuellement présent en constante est un héritage à déplacer dans les secrets lors de la mise en production ; la logique métier n'a pas été changée dans ce lot.

La version actuelle reste centrée sur le JSON détenu par le bénéficiaire. L'intégration Hub préparée n'impose pas encore une persistance serveur des réponses métier. Toute future persistance devra être placée hors du dossier écrasable par `git pull`, conformément au Framework VPS Clarté360 V1.
