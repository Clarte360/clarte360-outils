# Déploiement VPS — PIP RIASEC + O*NET

Référentiel: FRAMEWORK VPS CLARTÉ360 V1.0.

## Dossier stable
`/opt/clarte360/clarte360-outils/clarte360-pip-riasec-onet-v1.0.0/`

Les futurs incréments L2/L3 ou correctifs ne changent pas ce dossier tant qu'une migration explicite de dossier n'est pas décidée. La version est portée par le code et le CHANGELOG.

## Séparation obligatoire
- Code Git: dossier applicatif, `clarte360_pip/`, `resources/`, `tests/`, docs et scripts.
- Environnement: `.venv/` local à cette application, hors Git.
- Secrets: `.streamlit/secrets.toml`, hors Git. Sur VPS, créer de préférence un lien symbolique vers `/opt/clarte360/secrets/secrets.toml`.
- Données persistantes: `data/`, hors Git. Elles survivent aux `git pull`.
- Temporaire: `/tmp/clarte360-pip-riasec-onet`, hors Git.

## Première installation uniquement
```bash
cd /opt/clarte360/clarte360-outils/clarte360-pip-riasec-onet-v1.0.0
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
mkdir -p data .streamlit
ln -s /opt/clarte360/secrets/secrets.toml .streamlit/secrets.toml
```
Ne pas recréer le lien s'il existe déjà et pointe vers le bon fichier.

## Cycle standard de déploiement
```bash
cd /opt/clarte360/clarte360-outils/clarte360-pip-riasec-onet-v1.0.0
git status
git pull origin main
PYTHONPATH=. .venv/bin/pytest -q
.venv/bin/python -m py_compile app.py $(find clarte360_pip -name '*.py' -type f | sort)
sudo systemctl restart clarte360-pip-riasec-onet.service
sudo systemctl is-active clarte360-pip-riasec-onet.service
```

## Service systemd
Le fichier `clarte360-pip-riasec-onet.service.example` est un modèle documentaire. Le véritable service est créé sur le VPS et n'est pas un secret, mais il reste une configuration d'infrastructure locale.

## Persistance
Le code n'écrit aucune ressource métier versionnée dans `data/`. La banque PIP runtime et les schémas sont sous `resources/`, suivis par Git. Toute future donnée bénéficiaire, base locale, rapport ou export persistant doit être écrite sous `data/` ou vers un emplacement explicitement configuré par `CLARTE360_PIP_DATA_DIR`.

## Retour arrière
Un retour arrière Git porte uniquement sur le code. Les données persistantes doivent disposer d'une sauvegarde indépendante avant toute future migration destructive.
