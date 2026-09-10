# Rapport de tests automatises - L1-A

Date : 2026-09-10
Version : 0.1.0-l1a

Commandes executees :

```bash
python -m compileall -q app.py clarte360_pip tests scripts
python scripts/check_sources.py
python -m pytest -q
```

Resultats :

- Compilation Python : OK.
- Inventaire des 4 sources PIP cumulatives : OK.
- Tests unitaires : **14 passed**.
- Controle des modes PUBLIC/ACCOMPAGNEMENT : OK.
- Controle absence de secrets reels dans les fichiers texte : OK.
- Controle configuration O*NET absente en developpement : OK.
- Controle sauvegarde JSON technique : OK.
- Controle timeout : OK.
- Controle ports O*NET/ROME/Gestion des actions inactifs mais explicites : OK.
- Controle absence d'items pilotes integres prematurement dans le code runtime L1-A : OK.

Le serveur Streamlit n'a pas ete execute dans l'environnement de construction, la dependance `streamlit` n'y etant pas installee. La conformite de dependances est alignee sur Moteurs Professionnels V1.8 et sera verifiee en environnement applicatif/VPS lors de la consolidation prevue.
