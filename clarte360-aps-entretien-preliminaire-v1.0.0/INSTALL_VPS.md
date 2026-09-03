# Installation VPS Clarté360 — proposition

Cette application est conçue pour suivre l’architecture actuellement utilisée sur le VPS Clarté360 : GitHub → VPS → service systemd → Nginx → HTTPS Certbot.

## Emplacement proposé

`/opt/clarte360/clarte360-outils/clarte360-aps-entretien-preliminaire`

## Port interne proposé

`127.0.0.1:8502` (à confirmer qu’il est libre avant installation).

## Sous-domaine proposé

`aps.clarte360.com` (à créer dans les DNS OVH avant Certbot).

## Persistance recommandée

Créer : `/opt/clarte360/data/aps/`

Puis dans le fichier central `/opt/clarte360/secrets/secrets.toml` :

```toml
[database]
path = "/opt/clarte360/data/aps/clarte360_aps.db"
```

Ne pas ajouter de secret réel dans GitHub.

## Lien vers secrets centralisés

Dans le dossier de l’application :

```bash
mkdir -p .streamlit
ln -sfn /opt/clarte360/secrets/secrets.toml .streamlit/secrets.toml
```

## Installation Python

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

## Service systemd

Adapter puis copier `deploy/clarte360-aps.service.example` dans `/etc/systemd/system/clarte360-aps.service`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now clarte360-aps.service
systemctl --no-pager --full status clarte360-aps.service
```

## Nginx / HTTPS

Adapter `deploy/aps.clarte360.com.nginx.example`, activer le site, tester Nginx, puis lancer Certbot pour le sous-domaine.

## Sauvegarde

Inclure `/opt/clarte360/data/aps/clarte360_aps.db` dans la sauvegarde applicative VPS et tester une restauration.
