# Rapport de tests — Jalon H3.2 — 2026-09-19

## Commande
`python3 -m pytest -q`

## Résultat
- 196 tests exécutés
- 196 réussis
- 0 échec

## Contrôles spécifiques H3.2
- absence d'iframe PDF `data:` dans `pages.py` ;
- affichage Streamlit via `st.image` ;
- rendu serveur des pages 3 et 4 ;
- appel `pdftoppm` avec plage `-f 3 -l 4` ;
- maintien du bouton « J’ai consulté ma synthèse — donner mon ressenti » ;
- maintien du téléchargement du PDF complet ;
- maintien des tests H3.1 d'idempotence `study_id` ;
- maintien des tests H3 de séparation CRM / étude ;
- maintien de l'ensemble des tests antérieurs.
