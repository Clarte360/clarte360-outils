# Rapport de tests — CRM0 RC2 — 2026-09-19

- Compilation Python : OK (`app.py`, `services.py`, `db.py`, `branding.py`)
- Tests ciblés CRM0 RC1 + RC2 : 4 réussis / 4
- Suite complète : 362 réussis / 362
- Échecs : 0

## Tests RC2 ajoutés
- suppression d’une note ;
- modification puis suppression d’une tâche ;
- rattachement puis détachement d’une action sans suppression de l’action ;
- purge complète d’une fiche CRM avec cascade du contenu CRM ;
- vérification explicite que l’action métier liée reste présente après purge CRM.
