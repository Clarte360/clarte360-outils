# RAPPORT DE TESTS — INTERVENANTS J15
Date : 21/09/2026

## Résultat
**431 tests passés — 0 échec**.

La suite complète a été exécutée en trois lots pour éviter la limite de durée d’un lancement monolithique :
- lot 1 : 236 tests passés ;
- lot 2 : 113 tests passés ;
- lot 3 : 82 tests passés.

## Tests J15 spécifiques
- familles initiales et backfill des 26 prestations ;
- renommage d’une famille avec propagation aux prestations ;
- refus de suppression d’une famille utilisée sans destination ;
- fusion/suppression avec réaffectation ;
- réaffectation en masse ;
- présence d’au moins un critère actif et obligatoire pour chaque prestation ;
- absence de création automatique de qualification humaine ;
- persistance de l’origine `ADAPTATION_CLARTE360` ;
- non-régression J14 documents / IA globale ;
- compilation `db.py`, `services.py`, `app.py` réussie.

## Contrôle référentiel initial
- 5 familles ;
- 26 prestations ;
- 152 critères actifs initialisés ;
- Bilan de compétences : 8 critères ;
- Formation : 6 critères par prestation ;
- Coaching : 6 critères par prestation ;
- Conseil : 5 critères par prestation ;
- Accompagnements : 5 critères par prestation.

## Conclusion
J15 est techniquement recevable pour enchaîner sur J16. La prévalidation IA des critères et la transformation des éléments repérés en preuves proposées ne sont volontairement pas déclarées terminées à ce jalon.
