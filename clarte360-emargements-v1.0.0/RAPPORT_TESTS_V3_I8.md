# RAPPORT TESTS V3 I8

Base de travail : V3.0.0-I7.

## Correctifs I8

- Gestion Teams visible et sélectionnable dès la création de l'action, avant saisie du calendrier.
- Activation Teams possible sans créneau ; le premier créneau futur fixe automatiquement la date d'effet et déclenche la synchronisation.
- Onglet Teams simplifié : état Microsoft 365 lisible et bouton de synchronisation manuelle de secours.
- Validation bloquée si le nombre réel de participants ne correspond pas au nombre prévu.
- Rattachement automatique à une identité bénéficiaire existante uniquement en cas de correspondance exacte nom + prénom + date de naissance ; cas ambigus conservés en validation manuelle.
- Ajout d'un participant sur une action active déjà planifiée : envoi immédiat de son planning uniquement à ce nouveau participant.
- Rafraîchissement immédiat après ajout d'un participant.
- Relances automatiques d'émargement supprimées de l'interface ; relances manuelles conservées.
- Espace bénéficiaire : questionnaires terminés téléchargeables en PDF et feuilles individuelles d'émargement accessibles.
- Parcours de création clarifié : création puis participants/intervenants/calendrier avant validation opérationnelle.

## Validation

- Compilation Python : OK.
- Suite existante I7 + tests I8 : **126 tests réussis**.
