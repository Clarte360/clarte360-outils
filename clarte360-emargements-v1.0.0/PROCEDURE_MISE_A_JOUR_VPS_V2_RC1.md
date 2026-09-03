# PROCÉDURE SIMPLE — MISE À JOUR VPS POUR RECETTE V2 RC1

Cette procédure vise une recette, pas une suppression de la sauvegarde V1.

1. Effectuer et conserver une sauvegarde complète de la base et des signatures avant toute opération.
2. Déposer/committer le contenu de la candidate V2 dans le dépôt GitHub prévu.
3. Sur le VPS :
```bash
cd /opt/clarte360/clarte360-outils
git pull
cd clarte360-emargements-v2.0.0-dev
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```
4. Vérifier le lien `.streamlit/secrets.toml` vers `/opt/clarte360/secrets/secrets.toml`. Ne jamais copier les secrets dans GitHub.
5. Avant démarrage, exécuter sur une copie si possible :
```bash
PYTHONPATH=. pytest -q
```
Résultat attendu pour RC1 : **35 passed**.
6. Redémarrer web + worker :
```bash
sudo systemctl restart clarte360-emargements.service
sudo systemctl restart clarte360-emargements-worker.service
systemctl --no-pager --full status clarte360-emargements.service clarte360-emargements-worker.service
```
7. Contrôler les journaux :
```bash
journalctl -u clarte360-emargements.service -n 80 --no-pager
journalctl -u clarte360-emargements-worker.service -n 80 --no-pager
```
8. Vérifier `https://emargements.clarte360.com` puis réaliser la check-list de recette.

En cas de blocage de migration, ne pas purger la base : arrêter les services et restaurer la sauvegarde selon `restore_backup.py` / la procédure de sauvegarde existante.
