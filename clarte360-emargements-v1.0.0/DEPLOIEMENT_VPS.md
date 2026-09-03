# Déploiement VPS OVH — Clarté360 Émargements

## Pré-requis
Ubuntu 24.04 LTS, Python 3.12+, Git, Nginx.

## Principe
GitHub -> `/opt/clarte360/clarte360-outils/clarte360-emargements-v2.0.0-dev` -> service systemd Streamlit + service systemd worker -> Nginx HTTPS.

## Installation

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git nginx
cd /opt/clarte360/clarte360-outils/clarte360-emargements-v2.0.0-dev
# git clone <VOTRE_REPO_GITHUB> .
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
mkdir -p .streamlit
ln -sfn /opt/clarte360/secrets/secrets.toml .streamlit/secrets.toml
```

Définir `base_url` avec le futur sous-domaine, une `setup_key` longue et la configuration SMTP OVH.

## Services
Copier les deux fichiers `systemd/*.service` vers `/etc/systemd/system/` en adaptant `User=` si nécessaire, puis :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now clarte360-emargements clarte360-emargements-worker
```

## Nginx
Proxy vers `127.0.0.1:8501`, puis certificat Let's Encrypt. La configuration exacte sera réalisée avec le nom de domaine choisi.
