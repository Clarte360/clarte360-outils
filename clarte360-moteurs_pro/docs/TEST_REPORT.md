# Rapport de tests — 1.8.1

Source 1.8.0 : aucun test automatisé fourni. La 1.8.1 ajoute les tests de validation, bornes, JSON, compatibilité du JSON 1.8.0 Streamlit Cloud, Hub HMAC/rôles et identité VPS. Compilation Python et intégrité ZIP contrôlées avant livraison.


## Complément 1.8.2 — garde-fou
Tests ajoutés sur l'empreinte métier stable, le réarmement après nouvelle réponse, la détection d'un curseur non validé, l'exclusion des données techniques et la désactivation explicite du handler navigateur lorsque l'état est sauvegardé.

## Complément 1.8.4 — reprise JSON

- test de décodage d'un JSON représentatif V1.8.0 Streamlit Cloud avec le référentiel courant ;
- test AST garantissant que `import_json_screen(active)` reçoit bien le référentiel actif et que `main()` lui transmet `active` ;
- test garantissant que la restauration positionne `code_verified=True` et crée une session `reprise_depuis_json` ;
- contrôle de l'identité VPS en statut production ;
- compilation Python de l'ensemble des fichiers livrés ;
- questionnaire, scoring et référentiel Excel non modifiés.

### Résultat V1.8.4

- `PYTHONPATH=. pytest -q` : **33 tests réussis**.
- compilation Python : **OK**.
- validation d'un JSON historique complet V1.8.0 (60/60 curseurs, code antérieurement validé) : **OK**.
- aucune modification du fichier Excel métier ni du moteur de scoring.

