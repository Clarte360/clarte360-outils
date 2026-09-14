# RAPPORT DE TESTS — Gestion des actions — I9-A

**Date : 12/09/2026**  
**Version : 3.0.0-I9-A**

## Base contrôlée

Source I8 : `clarte360-gestion-actions-v3.0.0-I8-rebuild(1).zip`.

## Tests automatisés

Commande :

```bash
PYTHONPATH=. pytest -q
```

Résultat :

**132 tests réussis / 132**

Les 126 tests de la base I8 restent présents. 6 tests I9-A ont été ajoutés :

1. création/restauration/révocation d'une session persistante avec stockage du hash uniquement ;
2. expiration et révocation globale des sessions d'une identité ;
3. migration `auth_sessions` additive et idempotente ;
4. journalisation d'une erreur UI avec message utilisateur non technique ;
5. génération PDF individuelle sans erreur `wrapOn` lorsqu'une image de signature est absente ;
6. contrôle source : présence du garde de module et absence de `st.exception` / exposition brute du bug PDF.

## Compilation

Commande :

```bash
python -m py_compile app.py db.py services.py worker.py graph_client.py mailer.py excel_import.py security.py pdf_utils.py persistent_session.py ui_guard.py backup.py restore_backup.py source_store.py branding.py
```

Résultat : **COMPILE_OK**.

## Recette réelle différée

Conformément à la décision projet, aucun déploiement VPS et aucune recette navigateur réelle n'ont été effectués à ce stade. Restent donc à confirmer lors de la recette finale :

- persistance F5 réelle sur navigateur pour ADMINISTRATEUR ;
- persistance F5 réelle sur navigateur pour INTERVENANT ;
- persistance F5 réelle sur navigateur pour BÉNÉFICIAIRE ;
- comportement des cookies sous le domaine HTTPS de production ;
- rendu Streamlit complet des messages d'incident.

Aucune modification VPS n'a été réalisée.
