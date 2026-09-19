# CLARTÉ360 PIP RIASEC / O*NET — Jalon H3.2

## Objet
Correctif de recette réelle du parcours PUBLIC après constat d'un blocage Microsoft Edge de la prévisualisation PDF intégrée en iframe.

## Base
H3.2 est construit exclusivement à partir de H3.1.

## Anomalie constatée
Le navigateur Edge bloque l'iframe utilisant une URL `data:application/pdf;base64,...`. Le PDF lui-même reste valide et téléchargeable, mais sa consultation intégrée avant le questionnaire de ressenti devient impossible.

## Correctif
- Suppression de l'iframe PDF dans le parcours PUBLIC.
- Génération du PDF inchangée.
- Rendu serveur des pages 3 et 4 du rapport via `pdftoppm` (Poppler), à 120 dpi.
- Affichage direct des deux pages sous forme d'images dans Streamlit.
- Conservation du bouton de téléchargement du PDF complet.
- Conservation du bouton « J’ai consulté ma synthèse — donner mon ressenti » après la consultation.

## Périmètre non modifié
Aucune modification de :
- banque 72 items ;
- scoring / code Holland ;
- ROME ;
- O*NET ;
- contenu ou version du rapport PIP ;
- contrats CRM / étude pseudonymisée H3/H3.1 ;
- mode ACCOMPAGNEMENT.

## Fichiers modifiés / ajoutés
- `clarte360_pip/ui/pages.py`
- `clarte360_pip/pdf_preview.py` (nouveau)
- `tests/test_jalon_h2_feeling_after_report.py`
- `tests/test_jalon_h3_public_separation.py`
- `tests/test_jalon_h32_browser_safe_preview.py` (nouveau)
- `CHANGELOG.md`

## Dépendance système
La prévisualisation utilise `pdftoppm`, fourni par `poppler-utils`. Ce paquet est déjà installé sur le VPS Clarté360 dans le cadre des tests PDF H1.

## Résultat
196 tests réussis, 0 échec.
