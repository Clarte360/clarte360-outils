# Rapport de tests — V3.0.0-I1

Date : 05 septembre 2026

## Résultat

```text
85 passed
```

## Contrôles complémentaires

Compilation Python réussie :

```text
app.py
worker.py
services.py
db.py
```

## Tests spécifiques I1 ajoutés

- présence des nouvelles tables additives ;
- conservation des colonnes V2 ;
- migration V2 -> référent V3 ;
- migration V2 -> affectation par créneau ;
- historique de migration ;
- idempotence de la migration ;
- synchronisation `trainer_id` V2 / affectations V3 ;
- héritage du référent lors de la création d’un nouveau créneau ;
- synchronisation des modules ;
- Teams non activé automatiquement, y compris pour une action distancielle ;
- désaffectation sans suppression d’historique.
