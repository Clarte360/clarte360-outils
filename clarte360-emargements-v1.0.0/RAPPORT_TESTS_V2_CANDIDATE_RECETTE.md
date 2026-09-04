# RAPPORT TESTS — CLARTÉ360 ÉMARGEMENTS V2.2-RC1

Date : 4 septembre 2026

## Base contrôlée
Candidate construite exclusivement à partir du ZIP `V2.2 Lot 3 - fin d'action + qualité` fourni pour ce passage en recette complète.

Dossier interne conservé : `clarte360-emargements-v1.0.0`.

## Résultats automatisés
Commande utilisée :

```bash
python -m pytest -q
```

Résultat : **75 passed**.

Compilation complémentaire réussie pour : `app.py`, `db.py`, `worker.py`, `services.py`, `mailer.py`, `pdf_utils.py`, `excel_import.py`, `source_store.py`, `security.py`, `branding.py`, `backup.py`, `restore_backup.py`.

## Contrôles de consolidation ajoutés
- schéma additif des transmissions client et de la rétention portail ;
- anti-doublon des transmissions client ;
- transmission worker avec ZIP réellement passé en pièce jointe au moteur email ;
- avertissement puis purge du portail avec délai ;
- blocage de la purge lorsqu'une nouvelle action existe ;
- version applicative `2.2-RC1` ;
- contrôle AST de `app.py` : aucune expression conditionnelle Streamlit utilisée comme instruction autonome ;
- absence de chaîne `DeltaGenerator` dans les modules applicatifs.

## Point nécessitant recette VPS réelle
La connexion SMTP réelle ne peut pas être testée dans l'environnement de fabrication de la candidate, car les secrets Clarté360 restent volontairement hors du ZIP et hors GitHub. Le worker et les pièces jointes sont testés avec SMTP simulé ; l'envoi réel doit être validé sur le VPS avec les secrets existants.
