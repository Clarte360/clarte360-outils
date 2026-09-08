# RAPPORT DE TESTS — V3 I7 Microsoft Teams / Graph

Date : 05/09/2026

## Résultat automatisé

`122 passed`

## Couverture I7 ajoutée

- schéma Teams additif ;
- Teams jamais déduit automatiquement du mode online ;
- activation prospective au prochain créneau futur ;
- exclusion des créneaux antérieurs à la date d'effet ;
- création d'un lien stable d'action unique et réutilisation ;
- préparation multi-intervenants des rôles Teams ;
- récupération / stockage d'un rapport de présence simulé Graph ;
- rapprochement présence Teams / émargement ;
- absence de conversion automatique de présence en signature ;
- conservation des preuves Teams après désactivation du module ;
- configuration par certificat et absence de secret client dans le code ;
- exécution Graph indépendante du moteur SMTP.

## Compilation

Compilation Python réussie de :
- `app.py`
- `worker.py`
- `services.py`
- `db.py`
- `graph_client.py`
- `pdf_utils.py`
- `excel_import.py`
- `source_store.py`

## Limite de la recette

Les tests Graph automatisés utilisent un client simulé et valident le contrat du code sans appeler le tenant Microsoft réel.

La recette Microsoft réelle prévue au cahier des charges reste obligatoire avant activation de Teams en production, notamment pour le lien stable multi-occurrences, les Guests/co-organisateurs, le lobby et les rapports de présence réels.
