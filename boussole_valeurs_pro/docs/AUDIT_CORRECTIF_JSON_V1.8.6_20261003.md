# Audit et correctif JSON — Boussole des valeurs professionnelles v1.8.6

Date : 2026-10-03

## Anomalie
La v1.8.5 stockait `exit_json_bytes` au clic sur « Préparer mon JSON ». Si le bénéficiaire modifiait ensuite son questionnaire, le bouton « Télécharger le JSON préparé » pouvait encore servir cette ancienne copie, puis le mécanisme de garde-fou pouvait marquer l'état métier courant comme sauvegardé.

## Correctif
- aucune copie binaire de JSON n'est conservée dans `st.session_state` pour la sidebar ;
- le JSON sidebar est recalculé depuis `st.session_state.data` à chaque rerun ;
- toutes les sorties JSON utilisent `json_snapshot_bytes()` ;
- chaque bouton de téléchargement passe l'empreinte métier du contenu rendu au callback ;
- si l'empreinte ne correspond plus à l'état courant, le travail n'est pas marqué comme sauvegardé et un nouveau téléchargement est demandé.

## Compatibilité
Aucune clé métier du JSON n'est ajoutée, supprimée ou renommée. Les JSON v1.8.5 restent importables.

## Contrôles sur la copie de travail
- `python -m py_compile app.py validation.py hub_contract.py` : OK
- `PYTHONPATH=. pytest -q` : 49 tests réussis

## Déploiement VPS
La mise à jour GitHub n'est pas un déploiement automatique du VPS. Après intégration sur `main` :

```bash
cd /opt/clarte360/clarte360-outils/boussole_valeurs_pro
git status
git pull origin main
.venv/bin/python -m py_compile app.py validation.py hub_contract.py
PYTHONPATH=. .venv/bin/pytest -q
sudo systemctl restart clarte360-boussole-valeurs.service
sudo systemctl status clarte360-boussole-valeurs.service --no-pager
```
