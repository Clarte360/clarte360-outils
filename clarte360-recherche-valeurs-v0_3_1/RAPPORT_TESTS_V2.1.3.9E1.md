# Rapport de tests V2.1.3.9E1-preproduction

## Contrôles exécutés

- compilation Python de `app.py` ;
- exécution de l’intégralité de la suite Pytest ;
- exécution réelle de la fonction `_text_difference_kind` sur :
  - texte identique ;
  - ponctuation légère ;
  - cas contractuel « intégrité physique / ne manquer de rien » ;
  - reformulation réellement différente ;
- contrôle du gestionnaire navigateur Ctrl + Entrée ;
- contrôle de son branchement sur « Préparer et comparer » ;
- contrôle de l’utilisation du classificateur dans les parcours initiaux texte et voix.

## Résultat

- `python -m py_compile app.py` : réussi ;
- `python -m pytest -q` : **82 tests réussis, 0 échec**.

## Limites honnêtes

Les tests automatisés ne remplacent pas un essai visuel dans le navigateur. Le raccourci Ctrl + Entrée doit encore être vérifié dans l’environnement Streamlit cible, notamment selon le navigateur et la politique d’intégration des composants HTML. Les parcours vocaux nécessitent également un essai avec microphone et API de transcription disponibles.
