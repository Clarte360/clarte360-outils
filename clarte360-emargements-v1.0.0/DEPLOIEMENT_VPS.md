# Déploiement VPS — Clarté360 Gestion des Actions / Émargements

## Statut

Ce package est une **mise à jour de l'application existante** Gestion des Actions / Émargements.
Il ne crée ni nouvelle application, ni nouveau sous-domaine, ni nouveau port, ni nouveau service.

Référentiel VPS contrôlé : `FRAMEWORK_VPS_CLARTE360_V1.3.md`.

- URL officielle : `https://emargements.clarte360.com`
- Port interne : `8501`
- Service web : `clarte360-emargements.service`
- Service worker : `clarte360-emargements-worker.service`
- Dossier stable : `/opt/clarte360/clarte360-outils/clarte360-emargements-v1.0.0/`
- Secrets centralisés : `/opt/clarte360/secrets/secrets.toml`

## Principe de mise à jour

Le nom du ZIP de livraison évolue, mais **le dossier stable VPS ne change pas**.
La mise à jour doit préserver la base de données, les documents, signatures, sauvegardes et secrets existants.

## Contrôles avant mise à jour

1. Sauvegarder la base, les signatures et les fichiers persistants.
2. Vérifier l'état des services :

```bash
sudo systemctl is-active clarte360-emargements.service clarte360-emargements-worker.service
```

3. Vérifier que le port 8501 correspond toujours au service Gestion des Actions / Émargements.
4. Vérifier le lien `.streamlit/secrets.toml` vers `/opt/clarte360/secrets/secrets.toml`.
5. Ne jamais copier de secret dans GitHub, le ZIP ou les journaux.

## Mise à jour du code

Le code validé doit être déposé dans le dépôt GitHub de l'application puis récupéré dans le dossier stable :

```bash
cd /opt/clarte360/clarte360-outils/clarte360-emargements-v1.0.0
git status
git pull
. .venv/bin/activate
pip install -r requirements.txt
```

Ne pas recréer le dossier de production sous un nouveau nom et ne pas recréer inutilement le `.venv`.

## Validation avant redémarrage

```bash
cd /opt/clarte360/clarte360-outils/clarte360-emargements-v1.0.0
. .venv/bin/activate
python -m compileall -q .
python -m pytest -q
```

Résultat de référence J13 : **423 tests réussis, 0 échec**.

## Redémarrage

```bash
sudo systemctl daemon-reload
sudo systemctl restart clarte360-emargements.service clarte360-emargements-worker.service
sudo systemctl is-active clarte360-emargements.service clarte360-emargements-worker.service
```

## Contrôles après redémarrage

```bash
curl -I http://127.0.0.1:8501
journalctl -u clarte360-emargements.service -n 100 --no-pager
journalctl -u clarte360-emargements-worker.service -n 100 --no-pager
```

Puis vérifier :

- `https://emargements.clarte360.com` ;
- connexion administrateur ;
- ouverture d'une action existante ;
- onglet Intervenants & partenaires ;
- création/édition d'un dossier professionnel ;
- qualification humaine ;
- appel IA avec secrets VPS ;
- matrice collective ;
- CV Clarté360 ;
- affectation d'un intervenant à une action ;
- émargements, contresignatures, qualité, Teams et prescriptions historiques.

## Retour arrière

En cas d'anomalie bloquante : arrêter les services, restaurer le code précédent et la sauvegarde si une migration de données doit être annulée. Ne jamais purger la base pour résoudre un échec de migration.
