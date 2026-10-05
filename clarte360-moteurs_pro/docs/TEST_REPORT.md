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


## V1.8.6 — UX navigation / retour / audio — 05/10/2026
- Compilation : OK (`app.py`, `validation.py`, `hub_contract.py`, `work_guard.py`).
- Suite complète : 43 tests réussis.
- Contrôle AST : seuls `start_new_session`, `restore_from_progress`, `speak_button`, `sidebar_progress`, `questionnaire_screen` et `current_business_fingerprint` ont changé parmi les fonctions de `app.py`.
- Fonctions métier contrôlées inchangées : `compute_results`, `interpretation_level`, `build_payload`, `create_bar_chart`, `create_radar_chart`, `build_pdf`, `report_content_for`.
- XLSX métier SHA-256 inchangé : `59ccff89ded080d141a58b9c31a1fc290a7236daffaa9d84629c3446487f31b3`.
