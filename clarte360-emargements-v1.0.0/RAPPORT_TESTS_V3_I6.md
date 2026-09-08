# RAPPORT DE TESTS — V3 I6

Version testée : **Clarté360 — Gestion des actions V3.0.0-I6**

## Résultat

**114 tests réussis sur 114**.

Commande exécutée :

```bash
python -m pytest -q
```

Résultat :

```text
114 passed
```

## Contrôles I6 ajoutés
- présence du schéma `organization_import_profiles` ;
- profils isolés par organisme ;
- deux organismes peuvent utiliser le même code de profil avec des mappings différents ;
- lecteur Excel générique avec noms de colonnes totalement indépendants de Clarté360/ADCA ;
- rattachement automatique de l'import à l'organisme du profil ;
- profil par défaut idempotent et clé configurable ;
- stockage des snapshots isolé par profil ;
- chemin externe persistant par profil ;
- audit de création des profils ;
- absence des anciens onglets rigides Clarté360 / ADCA dans l'interface ;
- conservation de tous les tests I1 à I5 et de la V2.2.

## Compilation
Compilation réussie de :
- `app.py`
- `worker.py`
- `services.py`
- `db.py`
- `excel_import.py`
- `source_store.py`
- `pdf_utils.py`

## Sécurité / infrastructure
- aucune modification des secrets ;
- aucune modification de l'URL ;
- aucun changement de service systemd ;
- aucun changement du chemin VPS ;
- aucune intégration Teams commencée.
