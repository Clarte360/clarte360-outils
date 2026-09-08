# RAPPORT DE TESTS — V3 I2

**Date :** 05 septembre 2026  
**Version :** 3.0.0-I2 cumulative

## Résultat

- `pytest -q` : **88 tests réussis sur 88** ;
- compilation Python réussie : `app.py`, `worker.py`, `services.py`, `db.py`.

## Nouveaux scénarios I2 couverts

1. plusieurs intervenants sur une action et co-animation sur un créneau ;
2. accès intervenant basé sur les affectations V3 et visibilité des seuls créneaux affectés ;
3. remplacement d'intervenant avec conservation de l'affectation initiale et de l'historique ;
4. conservation des rôles et affectations lors d'un report puis d'un rattrapage ;
5. maintien des 85 tests cumulés antérieurs I1/V2.

Aucun déploiement VPS n'a été effectué.
