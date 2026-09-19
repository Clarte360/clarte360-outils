# Rapport de tests - CRM-0 RC1 - 2026-09-19

Base : `clarte360-gestion-actions-v3.0.0-I9-J2C-PIP-LIAISON-I-RECETTE-FINALE.zip` récupérée depuis OneDrive Clarté360 / 11 EMARGEMENTS.

## Résultat
- Suite complète exécutée en 3 lots pour éviter le timeout de session : **360 tests réussis, 0 échec**.
- Lot 1 : 154 réussis.
- Lot 2 : 95 réussis.
- Lot 3 : 111 réussis.
- Compilation Python : OK (`app.py`, `services.py`, `db.py`, `branding.py`).

## Recettes ciblées CRM-0
- `marketing_opt_in=true` PIP PUBLIC devient bien `marketing_consent=1` dans le CRM.
- `rgpd_text_version` est repris comme version RGPD CRM.
- `PIP-RIASEC` et `Solutions collectives pour mon entreprise` sont conservés ensemble dans les centres d'intérêt.
- Ajout note CRM : OK.
- Création/fermeture tâche commerciale : OK.
- Rattachement contact CRM <-> action : OK.
- Passage du contact au statut CLIENT lors du premier rattachement d'action : OK.

## Périmètre non modifié
Calendar/Teams, émargements, qualité, documents, étude PIP/O*NET pseudonymisée, contractualisation et moteur bénéficiaires n'ont pas été refactorés.
