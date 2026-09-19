# Rapport de tests - Jalon H3.1 - 19/09/2026

## Suite complete
Commande : `python -m pytest -q`

Resultat : **193 passed, 0 failed**.

## Nouveaux controles H3.1
- Le `public_study_id` est persiste dans une sauvegarde JSON PUBLIC.
- Les 72 reponses restent restaurees sans relancer le questionnaire.
- Une sauvegarde terminee reprend sur `finished`.
- Le `public_study_id` est restaure a l'identique.
- Le meme JSON recharge deux fois produit une seule etude logique et un seul fichier `<study_id>.json`.
- Le `study_id` ne fuit pas dans l'identite CRM du snapshot.
- Les garde-fous H3 CRM / etude continuent a passer.
- La correction H2 rapport avant ressenti continue a passer.

## Perimetre volontairement non traite
Pas de migration complexe des anciens JSON H1/H2 sans `public_study_id`, conformement a la decision de recette : bases d'essai videes avant la nouvelle recette reelle.
